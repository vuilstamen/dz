import pygame
import numpy as np
import sys
import os
import glob
import matplotlib
matplotlib.use('Agg')  # Используем фоновый режим для matplotlib
import matplotlib.pyplot as plt

def get_input(prompt, cast_type, default_value):
    """Безопасный ввод пользователя с проверкой типа и значением по умолчанию."""
    while True:
        user_input = input(prompt)
        if not user_input:
            return default_value
        try:
            value = cast_type(user_input)
            if isinstance(value, float) and not (0.0 <= value <= 1.0):
                print("Значение должно быть в диапазоне от 0 до 1.")
                continue
            if isinstance(value, int) and value <= 0:
                print("Значение должно быть больше 0.")
                continue
            return value
        except ValueError:
            print(f"Некорректный ввод. Ожидается {cast_type.__name__}.")

def get_moves(grid, car_id, axis, direction):
    """
    Вычисляет маски движения для легковых машин.
    direction: 1 (Восток/Юг) или -1 (Запад/Север).
    Возвращает три маски: move_1, move_2, move_3.
    """
    ahead_1 = np.roll(grid, -direction, axis=axis)
    ahead_2 = np.roll(grid, -2 * direction, axis=axis)
    ahead_3 = np.roll(grid, -3 * direction, axis=axis)
    
    is_car = (grid == car_id)
    
    move_3 = is_car & (ahead_1 == 0) & (ahead_2 == 0) & (ahead_3 == 0)
    move_2 = is_car & ~move_3 & (ahead_1 == 0) & (ahead_2 == 0)
    move_1 = is_car & ~move_3 & ~move_2 & (ahead_1 == 0)
    
    return move_1, move_2, move_3

def get_truck_moves(grid, front_id, mid_id, back_id, axis, direction):
    """
    Вычисляет маски движения для грузовиков (3 клетки).
    Проверяет возможность движения по передней клетке и распространяет на всю длину.
    """
    front_mask = (grid == front_id)
    mid_mask = (grid == mid_id)
    back_mask = (grid == back_id)
    
    ahead_1 = np.roll(grid, -direction, axis=axis)
    ahead_2 = np.roll(grid, -2 * direction, axis=axis)
    ahead_3 = np.roll(grid, -3 * direction, axis=axis)
    
    # Передняя часть может сдвинуться на 3, 2 или 1 клетку
    front_move_3 = front_mask & (ahead_1 == 0) & (ahead_2 == 0) & (ahead_3 == 0)
    front_move_2 = front_mask & ~front_move_3 & (ahead_1 == 0) & (ahead_2 == 0)
    front_move_1 = front_mask & ~front_move_3 & ~front_move_2 & (ahead_1 == 0)
    
    # Средняя и задняя части повторяют движение передней
    mid_move_3 = np.roll(front_move_3, -direction, axis=axis) & mid_mask
    mid_move_2 = np.roll(front_move_2, -direction, axis=axis) & mid_mask
    mid_move_1 = np.roll(front_move_1, -direction, axis=axis) & mid_mask
    
    back_move_3 = np.roll(front_move_3, -2 * direction, axis=axis) & back_mask
    back_move_2 = np.roll(front_move_2, -2 * direction, axis=axis) & back_mask
    back_move_1 = np.roll(front_move_1, -2 * direction, axis=axis) & back_mask
    
    return (front_move_1, mid_move_1, back_move_1,
            front_move_2, mid_move_2, back_move_2,
            front_move_3, mid_move_3, back_move_3)

def get_truck_uniform_moves(grid, front_id, mid_id, back_id, axis, direction, speed):
    """Вычисляет маски движения для грузовиков при равномерной скорости."""
    front_mask = (grid == front_id)
    mid_mask = (grid == mid_id)
    back_mask = (grid == back_id)
    
    can_move = np.ones_like(grid, dtype=bool)
    for k in range(1, speed + 1):
        can_move &= (np.roll(grid, -k * direction, axis=axis) == 0)
        
    front_move = front_mask & can_move
    mid_move = np.roll(front_move, -direction, axis=axis) & mid_mask
    back_move = np.roll(front_move, -2 * direction, axis=axis) & back_mask
    
    return front_move, mid_move, back_move

def place_trucks(grid, is_road, front_id, mid_id, back_id, axis, direction, density):
    """Размещает грузовики на сетке, проверяя, что 3 клетки подряд свободны и являются дорогой."""
    truck_front = (np.random.rand(*grid.shape) < density) & is_road & (grid == 0)
    valid = truck_front
    for k in range(1, 3):
        valid &= (np.roll(grid, -k * direction, axis=axis) == 0)
        valid &= (np.roll(is_road, -k * direction, axis=axis))
    
    grid[valid] = front_id
    grid[np.roll(valid, -direction, axis=axis)] = mid_id
    grid[np.roll(valid, -2 * direction, axis=axis)] = back_id

def calculate_jam(grid):
    """Считает количество машин, которые не могут сдвинуться с места (впереди занято)."""
    jam_red = np.sum((grid == 1) & (np.roll(grid, -1, axis=1) != 0)) + np.sum((grid == 11) & (np.roll(grid, -1, axis=1) != 0))
    jam_yellow = np.sum((grid == 3) & (np.roll(grid, 1, axis=1) != 0)) + np.sum((grid == 31) & (np.roll(grid, 1, axis=1) != 0))
    jam_blue = np.sum((grid == 2) & (np.roll(grid, -1, axis=0) != 0)) + np.sum((grid == 21) & (np.roll(grid, -1, axis=0) != 0))
    jam_green = np.sum((grid == 4) & (np.roll(grid, 1, axis=0) != 0)) + np.sum((grid == 41) & (np.roll(grid, 1, axis=0) != 0))
    
    return int(jam_red + jam_yellow + jam_blue + jam_green)

def main():
    print("=== Модель Манхэттенского трафика (Грузовики + Графики + GIF) ===")
    
    # 1. Получение параметров от пользователя
    road_spacing = get_input("Введите частоту дорог (каждая N-я клетка, например 10): ", int, 10)
    if road_spacing < 2:
        print("Частота дорог должна быть не менее 2. Установлено значение 2.")
        road_spacing = 2
        
    N = get_input("Введите размер квадратного поля (рекомендуется кратно частоте дорог): ", int, 60)
    T = get_input("Введите количество шагов симуляции (например, 100): ", int, 100)
    
    # Выбор типа дорог
    while True:
        rt = input("Выберите тип дорог (1 - по 2 полосы в каждую сторону, 2 - по 1 полосе каждые N клеток): ").strip()
        if rt == '':
            road_type = 1
            break
        if rt in ['1', '2']:
            road_type = int(rt)
            break
        print("Введите 1 или 2.")

    # Выбор типа движения
    move_type = input("Выберите тип движения (1 - равномерный, 2 - неравномерный): ").strip()
    uniform = (move_type != "2")
    uniform_speed = 1
    
    if uniform:
        print("Выбран равномерный режим.")
        while True:
            speed_input = input("Выберите скорость (1 - 1 клетка/шаг, 2 - 2 клетки/шаг, 3 - 3 клетки/шаг): ").strip()
            if speed_input in ['1', '2', '3']:
                uniform_speed = int(speed_input)
                break
            print("Введите 1, 2 или 3.")
    else:
        print("Выбран неравномерный режим: до 3 клеток за шаг в зависимости от свободного места.")

    p_red = get_input("Введите долю красных машин (Запад->Восток, 0..1): ", float, 0.3)
    p_blue = get_input("Введите долю синих машин (Юг->Север, 0..1): ", float, 0.3)
    
    if road_type == 1:
        p_yellow = get_input("Введите долю желтых машин (Восток->Запад, 0..1): ", float, 0.3)
        p_green = get_input("Введите долю зеленых машин (Север->Юг, 0..1): ", float, 0.3)
    else:
        print("Для типа дорог 2 желтые и зеленые машины отключены.")
        p_yellow = 0.0
        p_green = 0.0
        
    p_truck = get_input("Введите долю грузовиков среди всех машин (0..1, например 0.2 для 20%): ", float, 0.2)
    p_car = 1.0 - p_truck
        
    win_size = get_input("Введите начальный размер окна в пикселях (например, 800): ", int, 800)

    # 2. Инициализация сетки
    grid = np.zeros((N, N), dtype=np.int8)
    
    rows = np.arange(N)
    cols = np.arange(N)
    
    # Маски дорог в зависимости от выбора пользователя
    if road_type == 2:
        is_red_road = (rows[:, None] % road_spacing == 0)     
        is_yellow_road = np.zeros((N, N), dtype=bool) 
        is_blue_road = (cols[None, :] % road_spacing == 0)     
        is_green_road = np.zeros((N, N), dtype=bool) 
    else:
        is_red_road = (rows[:, None] % road_spacing == 0)     
        is_yellow_road = (rows[:, None] % road_spacing == 1)  
        is_blue_road = (cols[None, :] % road_spacing == 0)    
        is_green_road = (cols[None, :] % road_spacing == 1)  
    
    is_road = is_red_road | is_yellow_road | is_blue_road | is_green_road
    grid[~is_road] = 5 # Здания
    
    # Размещаем легковые машины (с учетом доли грузовиков)
    grid[(np.random.rand(N, N) < p_red * p_car) & is_red_road & (grid == 0)] = 1
    grid[(np.random.rand(N, N) < p_yellow * p_car) & is_yellow_road & (grid == 0)] = 3
    grid[(np.random.rand(N, N) < p_blue * p_car) & is_blue_road & (grid == 0)] = 2
    grid[(np.random.rand(N, N) < p_green * p_car) & is_green_road & (grid == 0)] = 4

    # Размещаем грузовики (3 клетки: передняя, средняя, задняя)
    # ID грузовиков: Красные - 11, 12, 13; Синие - 21, 22, 23; Желтые - 31, 32, 33; Зеленые - 41, 42, 43
    place_trucks(grid, is_red_road, 11, 12, 13, 1, 1, p_red * p_truck)
    place_trucks(grid, is_blue_road, 21, 22, 23, 0, -1, p_blue * p_truck)
    if road_type == 1:
        place_trucks(grid, is_yellow_road, 31, 32, 33, 1, -1, p_yellow * p_truck)
        place_trucks(grid, is_green_road, 41, 42, 43, 0, 1, p_green * p_truck)

    # Подсчет общего числа машин для масштаба графика (грузовик считается как 1 машина)
    car_count = np.sum((grid > 0) & (grid < 5))
    truck_count = np.sum((grid == 11) | (grid == 21) | (grid == 31) | (grid == 41))
    total_cars = max(1, int(car_count + truck_count))

    # 3. Настройка Pygame и папок для кадров
    frames_dir = "frames_simulation"
    graph_dir = "frames_graph"
    
    for d in [frames_dir, graph_dir]:
        if not os.path.exists(d):
            os.makedirs(d)
            
    pygame.init()
    panel_height = 40
    screen = pygame.display.set_mode((win_size, win_size + panel_height), pygame.RESIZABLE)
    pygame.display.set_caption("Клеточный автомат: Трафик с грузовиками")
    
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18)

    current_step = 0
    running = True
    simulation_active = True
    color_text = "Ожидание..."
    
    jam_history = []
    plt.figure(figsize=(5, 4), dpi=100)

    # 4. Главный цикл
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        # 5. Логика симуляции
        if simulation_active and current_step < T:
            phase = current_step % 2
            
            if phase == 0:
                # --- ХОД КРАСНЫХ И ЖЕЛТЫХ ---
                if uniform:
                    speed = uniform_speed
                    # Легковые
                    can_move_red = np.ones_like(grid, dtype=bool)
                    can_move_yellow = np.ones_like(grid, dtype=bool)
                    for k in range(1, speed + 1):
                        can_move_red &= (np.roll(grid, -k, axis=1) == 0)
                        can_move_yellow &= (np.roll(grid, k, axis=1) == 0)
                    m_red = (grid == 1) & can_move_red
                    m_yellow = (grid == 3) & can_move_yellow
                    
                    # Грузовики
                    r_f, r_m, r_b = get_truck_uniform_moves(grid, 11, 12, 13, 1, 1, speed)
                    y_f, y_m, y_b = get_truck_uniform_moves(grid, 31, 32, 33, 1, -1, speed)
                    
                    grid[m_red | m_yellow | r_f | r_m | r_b | y_f | y_m | y_b] = 0
                    grid[np.roll(m_red, speed, axis=1)] = 1
                    grid[np.roll(m_yellow, -speed, axis=1)] = 3
                    
                    grid[np.roll(r_f, speed, axis=1)] = 11
                    grid[np.roll(r_m, speed, axis=1)] = 12
                    grid[np.roll(r_b, speed, axis=1)] = 13
                    grid[np.roll(y_f, -speed, axis=1)] = 31
                    grid[np.roll(y_m, -speed, axis=1)] = 32
                    grid[np.roll(y_b, -speed, axis=1)] = 33
                else:
                    # Легковые
                    r1, r2, r3 = get_moves(grid, 1, 1, 1) 
                    y1, y2, y3 = get_moves(grid, 3, 1, -1) 
                    # Грузовики
                    r_trucks = get_truck_moves(grid, 11, 12, 13, 1, 1)
                    y_trucks = get_truck_moves(grid, 31, 32, 33, 1, -1)
                    
                    # Очистка старых позиций
                    grid[r1|r2|r3|y1|y2|y3|r_trucks[0]|r_trucks[1]|r_trucks[2]|r_trucks[3]|r_trucks[4]|r_trucks[5]|r_trucks[6]|r_trucks[7]|r_trucks[8]|
                         y_trucks[0]|y_trucks[1]|y_trucks[2]|y_trucks[3]|y_trucks[4]|y_trucks[5]|y_trucks[6]|y_trucks[7]|y_trucks[8]] = 0
                    
                    # Перемещение легковых
                    grid[np.roll(r1, 1, axis=1)] = 1
                    grid[np.roll(r2, 2, axis=1)] = 1
                    grid[np.roll(r3, 3, axis=1)] = 1
                    grid[np.roll(y1, -1, axis=1)] = 3
                    grid[np.roll(y2, -2, axis=1)] = 3
                    grid[np.roll(y3, -3, axis=1)] = 3
                    
                    # Перемещение грузовиков
                    for step in range(1, 4):
                        idx = (step - 1) * 3
                        # Красные
                        grid[np.roll(r_trucks[idx], step, axis=1)] = 11
                        grid[np.roll(r_trucks[idx+1], step, axis=1)] = 12
                        grid[np.roll(r_trucks[idx+2], step, axis=1)] = 13
                        # Желтые
                        grid[np.roll(y_trucks[idx], -step, axis=1)] = 31
                        grid[np.roll(y_trucks[idx+1], -step, axis=1)] = 32
                        grid[np.roll(y_trucks[idx+2], -step, axis=1)] = 33
                    
                color_text = "Красные и Желтые (Горизонталь)"
                
            elif phase == 1:
                # --- ХОД СИНИХ И ЗЕЛЕНЫХ ---
                if uniform:
                    speed = uniform_speed
                    # Легковые
                    can_move_blue = np.ones_like(grid, dtype=bool)
                    can_move_green = np.ones_like(grid, dtype=bool)
                    for k in range(1, speed + 1):
                        can_move_blue &= (np.roll(grid, k, axis=0) == 0)
                        can_move_green &= (np.roll(grid, -k, axis=0) == 0)
                    m_blue = (grid == 2) & can_move_blue
                    m_green = (grid == 4) & can_move_green
                    
                    # Грузовики
                    b_f, b_m, b_b = get_truck_uniform_moves(grid, 21, 22, 23, 0, -1, speed)
                    g_f, g_m, g_b = get_truck_uniform_moves(grid, 41, 42, 43, 0, 1, speed)
                    
                    grid[m_blue | m_green | b_f | b_m | b_b | g_f | g_m | g_b] = 0
                    grid[np.roll(m_blue, -speed, axis=0)] = 2
                    grid[np.roll(m_green, speed, axis=0)] = 4
                    
                    grid[np.roll(b_f, -speed, axis=0)] = 21
                    grid[np.roll(b_m, -speed, axis=0)] = 22
                    grid[np.roll(b_b, -speed, axis=0)] = 23
                    grid[np.roll(g_f, speed, axis=0)] = 41
                    grid[np.roll(g_m, speed, axis=0)] = 42
                    grid[np.roll(g_b, speed, axis=0)] = 43
                else:
                    # Легковые
                    b1, b2, b3 = get_moves(grid, 2, 0, -1) 
                    g1, g2, g3 = get_moves(grid, 4, 0, 1)  
                    # Грузовики
                    b_trucks = get_truck_moves(grid, 21, 22, 23, 0, -1)
                    g_trucks = get_truck_moves(grid, 41, 42, 43, 0, 1)
                    
                    # Очистка старых позиций
                    grid[b1|b2|b3|g1|g2|g3|b_trucks[0]|b_trucks[1]|b_trucks[2]|b_trucks[3]|b_trucks[4]|b_trucks[5]|b_trucks[6]|b_trucks[7]|b_trucks[8]|
                         g_trucks[0]|g_trucks[1]|g_trucks[2]|g_trucks[3]|g_trucks[4]|g_trucks[5]|g_trucks[6]|g_trucks[7]|g_trucks[8]] = 0
                    
                    # Перемещение легковых
                    grid[np.roll(b1, -1, axis=0)] = 2
                    grid[np.roll(b2, -2, axis=0)] = 2
                    grid[np.roll(b3, -3, axis=0)] = 2
                    grid[np.roll(g1, 1, axis=0)] = 4
                    grid[np.roll(g2, 2, axis=0)] = 4
                    grid[np.roll(g3, 3, axis=0)] = 4
                    
                    # Перемещение грузовиков
                    for step in range(1, 4):
                        idx = (step - 1) * 3
                        # Синие
                        grid[np.roll(b_trucks[idx], -step, axis=0)] = 21
                        grid[np.roll(b_trucks[idx+1], -step, axis=0)] = 22
                        grid[np.roll(b_trucks[idx+2], -step, axis=0)] = 23
                        # Зеленые
                        grid[np.roll(g_trucks[idx], step, axis=0)] = 41
                        grid[np.roll(g_trucks[idx+1], step, axis=0)] = 42
                        grid[np.roll(g_trucks[idx+2], step, axis=0)] = 43
                    
                color_text = "Синие и Зеленые (Вертикаль)"

            current_step += 1
            if current_step >= T:
                simulation_active = False
                color_text = "Симуляция завершена!"
                
            # 6. Подсчет пробок и сохранение графика
            current_jam = calculate_jam(grid)
            jam_history.append(current_jam)
            
            plt.clf() 
            plt.plot(jam_history, color='red', marker='.', linestyle='-')
            plt.xlabel("Шаг симуляции")
            plt.ylabel("Машин в пробке")
            plt.title("Динамика пробок")
            plt.xlim(0, T)
            plt.ylim(0, total_cars) 
            plt.grid(True)
            plt.tight_layout()
            
            graph_path = os.path.join(graph_dir, f"graph_{current_step:04d}.png")
            plt.savefig(graph_path)

        # 7. Отрисовка Pygame
        win_w, win_h = screen.get_size()
        sim_area_h = win_h - panel_height
        
        screen.fill((0, 0, 0), rect=pygame.Rect(0, 0, win_w, sim_area_h))
        screen.fill((45, 45, 45), rect=pygame.Rect(0, sim_area_h, win_w, panel_height))

        rgb_array = np.zeros((N, N, 3), dtype=np.uint8)
        rgb_array[grid == 0] = [180, 180, 180] 
        
        # Легковые
        rgb_array[grid == 1] = [220, 20, 60]   
        rgb_array[grid == 2] = [30, 144, 255]  
        rgb_array[grid == 3] = [255, 215, 0]   
        rgb_array[grid == 4] = [0, 200, 0]     
        
        # Грузовики (затемненные оттенки для средней и задней части)
        rgb_array[grid == 11] = [220, 20, 60]
        rgb_array[grid == 12] = [170, 15, 45]
        rgb_array[grid == 13] = [120, 10, 30]
        
        rgb_array[grid == 21] = [30, 144, 255]
        rgb_array[grid == 22] = [25, 110, 190]
        rgb_array[grid == 23] = [20, 80, 140]
        
        rgb_array[grid == 31] = [255, 215, 0]
        rgb_array[grid == 32] = [200, 165, 0]
        rgb_array[grid == 33] = [150, 120, 0]
        
        rgb_array[grid == 41] = [0, 200, 0]
        rgb_array[grid == 42] = [0, 150, 0]
        rgb_array[grid == 43] = [0, 100, 0]
        
        rgb_array[grid == 5] = [60, 60, 60]    

        surf = pygame.surfarray.make_surface(np.transpose(rgb_array, (1, 0, 2)))
        
        target_size = min(win_w, sim_area_h)
        if target_size > 0:
            surf_scaled = pygame.transform.scale(surf, (target_size, target_size))
            offset_x = (win_w - target_size) // 2
            offset_y = (sim_area_h - target_size) // 2
            screen.blit(surf_scaled, (offset_x, offset_y))
            
            if simulation_active or current_step >= T:
                frame_path = os.path.join(frames_dir, f"frame_{current_step:04d}.png")
                try:
                    pygame.image.save(surf_scaled, frame_path)
                except Exception as e:
                    print(f"Ошибка сохранения кадра: {e}")

        # Отрисовка текста
        move_type_text = f"Равномерное ({uniform_speed} кл/шаг)" if uniform else "Неравномерное"
        road_type_text = "1 полоса" if road_type == 2 else "2 полосы"
        info_text = f"Шаг: {current_step}/{T} | Дороги: {road_type_text} (кажд. {road_spacing}) | Грузовики: {int(p_truck*100)}% | {move_type_text} | Ходят: {color_text}"
        text_surface = font.render(info_text, True, (255, 255, 255))
        text_x = 10
        text_y = sim_area_h + (panel_height - text_surface.get_height()) // 2
        screen.blit(text_surface, (text_x, text_y))

        pygame.display.flip()
        clock.tick(15)

    pygame.quit()
    plt.close('all')

    # --- ИТОГОВЫЙ ГРАФИК ЕДИНОЙ ЛИНИЕЙ (не входит в GIF) ---
    # Имя файла выбрано так, чтобы не совпадать с шаблоном graph_*.png,
    # поэтому данный кадр не попадёт в GIF-анимацию графика.
    print("\nПостроение итогового графика (единой линией)...")

    # Пытаемся переключить бэкенд matplotlib на интерактивный,
    # чтобы можно было показать график в отдельном окне.
    backend_switched = False
    for backend_name in ['TkAgg', 'Qt5Agg', 'Qt4Agg', 'MacOSX']:
        try:
            plt.switch_backend(backend_name)
            backend_switched = True
            break
        except Exception:
            continue

    # Создаём итоговый график: одна сплошная линия, без точек-маркеров
    plt.figure(figsize=(8, 6), dpi=100)
    if jam_history:
        plt.plot(jam_history, color='red', linestyle='-', linewidth=2, label='Мгновенное кол-во машин в пробке')
        
        # Вычисляем среднее значение и добавляем синюю линию поверх графика
        avg_jam = np.mean(jam_history)
        plt.axhline(y=avg_jam, color='lime', linestyle='--', linewidth=2, label=f'Среднее кол-во машин в пробке: {avg_jam:.1f}')
        plt.legend()
        
    plt.xlabel("Шаг симуляции")
    plt.ylabel("Машин в пробке")
    plt.title("Итоговая динамика пробок")
    plt.xlim(0, T)
    plt.ylim(0, total_cars)
    plt.grid(True)
    plt.tight_layout()

    # Сохраняем итоговый график с именем, которое НЕ совпадает с шаблоном graph_*.png
    final_graph_path = os.path.join(graph_dir, "final_graph.png")
    plt.savefig(final_graph_path)
    print(f"Итоговый график сохранён: {final_graph_path}")

    # Показываем график пользователю
    if backend_switched:
        # Интерактивное окно matplotlib (блокирует до закрытия окна)
        plt.show()
    else:
        # Fallback: открыть через системный просмотрщик изображений (PIL)
        try:
            from PIL import Image
            Image.open(final_graph_path).show()
        except Exception as e:
            print(f"Не удалось открыть окно графика автоматически: {e}")
            print(f"Файл итогового графика доступен по пути: {final_graph_path}")

    # Закрываем фигуру, чтобы освободить ресурсы
    plt.close('all')

    # 8. Запрос на создание GIF для симуляции
    print("\nСимуляция завершена. Окно закрыто.")
    create_sim_gif = input("Создать GIF из сохраненных кадров симуляции? (y - да / n - нет): ").strip().lower()
    
    if create_sim_gif in ['y', 'yes', 'да', '1']:
        print("Создание GIF-анимации симуляции... Это может занять некоторое время.")
        try:
            from PIL import Image
            frames = []
            frame_paths = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
            for path in frame_paths:
                frames.append(Image.open(path))
            if frames:
                gif_path = os.path.join(frames_dir, "simulation.gif")
                frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)
                print(f"Готово! GIF симуляции сохранен по пути: {gif_path}")
            else:
                print("Кадры симуляции не найдены.")
        except ImportError:
            print("Ошибка: Библиотека Pillow не установлена. Установите её командой: pip install Pillow")
        except Exception as e:
            print(f"Произошла ошибка при создании GIF симуляции: {e}")
    else:
        print("GIF для симуляции не создается.")

    # 9. Запрос на создание GIF для графика
    create_graph_gif = input("Создать GIF из графиков пробок? (y - да / n - нет): ").strip().lower()
    
    if create_graph_gif in ['y', 'yes', 'да', '1']:
        print("Создание GIF-анимации графика... Это может занять некоторое время.")
        try:
            from PIL import Image
            graph_frames = []
            graph_paths = sorted(glob.glob(os.path.join(graph_dir, "graph_*.png")))
            for path in graph_paths:
                graph_frames.append(Image.open(path))
            if graph_frames:
                graph_gif_path = os.path.join(graph_dir, "graph_simulation.gif")
                graph_frames[0].save(graph_gif_path, save_all=True, append_images=graph_frames[1:], duration=100, loop=0)
                print(f"Готово! GIF графика сохранен по пути: {graph_gif_path}")
            else:
                print("Кадры графика не найдены.")
        except ImportError:
            print("Ошибка: Библиотека Pillow не установлена. Установите её командой: pip install Pillow")
        except Exception as e:
            print(f"Произошла ошибка при создании GIF графика: {e}")
    else:
        print("GIF для графика не создается.")

    sys.exit()

if __name__ == "__main__":
    main()