import sys
import io
import socket
import logging
import json
import base64
import pygame
import time

WIDTH, HEIGHT = 800, 600
FPS = 60

CHARACTER_SIZE = (48, 48)
GEM_SIZE = (20, 20)
HAZARD_DEFAULT_SIZE = (100, 50)
EXIT_SIZE = (80, 80)
WALL_UNIT_SIZE = 20
GRAVITY = 0.5
JUMP_STRENGTH = -10
TERMINAL_VELOCITY = 10
WHITE, BLACK, RED, GREY, WIN_GREEN, GREEN = (255, 255, 255), (0, 0, 0), (255, 0, 0), (150, 150, 150), (0, 200, 0), (0, 200, 0)

# ---Initialization ---
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Game of Bones")
clock = pygame.time.Clock()

# --- Fonts ---
FONT_PATH = 'assets/fonts/PixelGameFont.ttf'
font_large = pygame.font.Font(FONT_PATH, 74)
font_medium = pygame.font.Font(FONT_PATH, 36)
font_small = pygame.font.Font(FONT_PATH, 24)
font_ingame = pygame.font.Font(FONT_PATH, 20)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ClientInterface:
    """Handles communication with the game server."""

    def __init__(self):
        # self.server_address = ('127.0.0.1', 58123)
        # self.server_address = ('192.168.46.183', 58123)
        self.server_address = ('127.0.0.1', 8889)
        # self.server_address = ('57.155.89.38', 8889)


    def send_command(self, command_str=""):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(self.server_address)
            
            url_path = "/game/" + command_str.replace(" ", "/")
            
            request = (
                f"GET {url_path} HTTP/1.0\r\n"
                f"Host: {self.server_address[0]}:{self.server_address[1]}\r\n"
                f"Connection: close\r\n"
                "\r\n"
            )
            
            sock.sendall(request.encode('utf-8'))
            
            data_received = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data_received += chunk

            if not data_received:
                return {"status": "ERROR", "message": "Empty response from server"}

            header_end = data_received.find(b'\r\n\r\n')
            if header_end == -1:
                return {"status": "ERROR", "message": "Invalid HTTP response"}

            json_body = data_received[header_end + 4:]
            
            decoded_data = json_body.decode('utf-8').strip()
            if decoded_data:
                return json.loads(decoded_data)
            
            return {"status": "ERROR", "message": "Empty JSON body in response"}
            
        except json.JSONDecodeError:
            return {"status": "ERROR", "message": "Failed to decode JSON from server"}
        except Exception as e:
            return {"status": "ERROR", "message": f"Connection error: {e}"}
        finally:
            sock.close()

    def register_player(self, color): return self.send_command(f"register_player {color}")
    def set_player_state(self, player_id, x, y, lives): return self.send_command(f"set_player_state {player_id} {x} {y} {lives}")
    def get_game_state(self): return self.send_command("get_game_state")
    def collect_gem(self, player_id, gem_id): return self.send_command(f"collect_gem {player_id} {gem_id}")
    def check_hazard_collision(self, player_id, hazard_id): return self.send_command(f"check_hazard_collision {player_id} {hazard_id}")
    def player_at_exit(self, player_id): return self.send_command(f"player_at_exit {player_id}")
    def reset_game(self): return self.send_command(f"reset_game")


class GameObject:
    def __init__(self, id, x, y, size, image_b64, default_color=GREY):
        self.id = id
        self.rect = pygame.Rect(x, y, size[0], size[1])
        if image_b64:
            try:
                self.image = pygame.transform.scale(pygame.image.load(io.BytesIO(base64.b64decode(image_b64))), size)
            except Exception:
                self._set_default_image(size, default_color)
        else:
            self._set_default_image(size, default_color)

    def _set_default_image(self, size, color):
        self.image = pygame.Surface(size)
        self.image.fill(color)

    def draw(self, surface):
        surface.blit(self.image, self.rect)

class PlayerCharacter:
    def __init__(self, id, is_local_player=False, initial_color_choice=None):
        self.id, self.is_local_player = id, is_local_player
        self.color_type = initial_color_choice
        self.x, self.y, self.speed = 0, 0, 5
        self.gems_collected, self.lives, self.at_exit = 0, 1, False
        self.vy, self.on_ground, self.facing_left = 0, False, False
        self.is_dead = False
        
        self.target_x, self.target_y = 0, 0
        self.lerp_speed = 0.2

        self.animations, self.animation_speed = {}, 0.1
        self.last_update_time, self.current_frame_index = pygame.time.get_ticks(), 0
        
        asset_type = 'dog'
        if self.color_type == 'white': asset_type = 'cat'
        elif self.id and 'white' in self.id: asset_type = 'cat'

        self.animations['idle'] = self._load_sprite_sheet(f'assets/{asset_type}/Idle.png', 4)
        self.animations['walk'] = self._load_sprite_sheet(f'assets/{asset_type}/Walk.png', 6)
        self.animations['death'] = self._load_sprite_sheet(f'assets/{asset_type}/Death.png', 4)
        
        if self.animations['walk']:
            jump_fall_pose = [self.animations['walk'][0]]
            self.animations['jump'] = jump_fall_pose
            self.animations['fall'] = jump_fall_pose
        else:
            self.animations['jump'] = self.animations['idle']
            self.animations['fall'] = self.animations['idle']
        
        self.current_animation = 'idle'
        self.image = self.animations[self.current_animation][self.current_frame_index]
        self.rect = self.image.get_rect(topleft=(self.x, self.y))
        
        if self.is_local_player: self.client_interface = ClientInterface()
        logging.info(f"PlayerCharacter: Initialized {self.id} (Local: {self.is_local_player}, Color: {self.color_type})")

        try:
            self.death_sound = pygame.mixer.Sound('assets/sound/dead_sound.wav')
            self.get_gem_sound = pygame.mixer.Sound('assets/sound/get_gem.wav')
            self.Stagewin = pygame.mixer.Sound('assets/sound/Stagewin.mp3')
            self.winmatch = pygame.mixer.Sound('assets/sound/WINMATCH.mp3')
        except pygame.error as e:
            print(f"Peringatan: Tidak bisa memuat file suara. Error: {e}")
            self.death_sound = None
            self.get_gem_sound = None
            self.Stagewin = None

    def _load_sprite_sheet(self, filepath, frame_count):
        try:
            spritesheet = pygame.image.load(filepath).convert_alpha()
            w, h = spritesheet.get_width() // frame_count, spritesheet.get_height()
            return [pygame.transform.scale(spritesheet.subsurface(pygame.Rect(i * w, 0, w, h)), CHARACTER_SIZE) for i in range(frame_count)]
        except Exception as e:
            logging.error(f"Failed to load sprite: {filepath} - {e}")
            fallback = pygame.Surface(CHARACTER_SIZE)
            fallback.fill(RED)
            return [fallback]

    def set_animation(self, new_animation):
        if new_animation in self.animations and self.current_animation != new_animation:
            self.current_animation = new_animation
            self.current_frame_index = 0

    def update_animation(self):
        
        now = pygame.time.get_ticks()
        if now - self.last_update_time > self.animation_speed * 1000:
            self.last_update_time = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.animations[self.current_animation])
            new_image = self.animations[self.current_animation][self.current_frame_index]
            self.image = pygame.transform.flip(new_image, self.facing_left, False)

    def update(self):
        self.x += (self.target_x - self.x) * self.lerp_speed
        self.y += (self.target_y - self.y) * self.lerp_speed
        self.rect.topleft = (self.x, self.y)
        self.update_animation()

    def move(self, keys, walls):
        if self.is_dead: 
            return
        
        dx = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: dx, self.facing_left = -self.speed, True
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx, self.facing_left = self.speed, False

        if not self.on_ground:
            self.set_animation('jump' if self.vy < 0 else 'fall')
        else:
            self.set_animation('walk' if dx != 0 else 'idle')
        
        self.vy += GRAVITY
        self.vy = min(self.vy, TERMINAL_VELOCITY)
        if self.on_ground and (keys[pygame.K_UP] or keys[pygame.K_w]):
            self.vy, self.on_ground = JUMP_STRENGTH, False
            self.set_animation('jump')
        
        self.rect.x += dx
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if dx > 0: self.rect.right = wall.rect.left
                elif dx < 0: self.rect.left = wall.rect.right
        
        self.rect.y += self.vy
        self.on_ground = False
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if self.vy > 0: self.rect.bottom, self.vy, self.on_ground = wall.rect.top, 0, True
                elif self.vy < 0: self.rect.top, self.vy = wall.rect.bottom, 0
        
        self.x, self.y = self.rect.x, self.rect.y
        self.client_interface.set_player_state(self.id, self.x, self.y, self.lives)

    def update_from_server(self, p_data):
        just_got_hit = p_data['lives'] < self.lives
        is_dead_on_server = p_data.get('is_dead', False)
        self.is_dead = is_dead_on_server 

        if just_got_hit and self.death_sound:
            self.death_sound.play()

        self.target_x, self.target_y = p_data['x'], p_data['y']
        self.lives = p_data['lives']
        self.gems_collected = p_data['gems_collected']
        self.at_exit = p_data['at_exit']
        
        if self.is_local_player:
            self.x, self.y = p_data['x'], p_data['y']
            self.rect.topleft = (self.x, self.y)

        if self.is_dead:
            self.set_animation('death')
        else:
            is_moving_horizontally = abs(self.rect.x - self.target_x) > 1
            is_in_air = abs(self.rect.y - self.target_y) > 5
            
            if is_in_air and not self.on_ground:
                 self.set_animation('fall')
            elif is_moving_horizontally:
                self.set_animation('walk')
            else:
                self.set_animation('idle')

    def draw(self, surface):
        if self.image: surface.blit(self.image, self.rect)

class Gem(GameObject):
    def __init__(self, id, x, y, gem_type, image_b64):
        self.gem_type = gem_type
        super().__init__(id, x, y, GEM_SIZE, image_b64, WHITE if gem_type == 'white' else BLACK)

class Hazard(GameObject):
    def __init__(self, id, x, y, hazard_type, width, height, image_b64):
        self.hazard_type = hazard_type
        super().__init__(id, x, y, (width, height), image_b64, RED)

class ExitArea(GameObject):
    def __init__(self, x, y, width, height, image_b64):
        super().__init__('exit_area', x, y, (width, height), image_b64, WIN_GREEN)

class Wall(GameObject):
    def __init__(self, id, x, y, width, height, image_b64):
        super().__init__(id, x, y, (width, height), image_b64, GREY)


def show_start_screen():
    """Menampilkan layar awal dengan animasi teks."""
    try:
        background_img = pygame.image.load('assets/bg/awal.png').convert()
        background_img = pygame.transform.scale(background_img, (WIDTH, HEIGHT))
    except pygame.error as e:
        print(f"Error memuat background awal: {e}")
        background_img = None

    start_text = font_medium.render("click space to start", True, WHITE)
    text_rect = start_text.get_rect(center=(WIDTH // 2, HEIGHT - 80))
    last_blink_time = 0
    blink_interval = 500 
    text_visible = True
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    running = False 

        current_time = pygame.time.get_ticks()
        if current_time - last_blink_time > blink_interval:
            text_visible = not text_visible
            last_blink_time = current_time

        if background_img:
            screen.blit(background_img, (0, 0))
        else:
            screen.fill(BLACK) 
        if text_visible:
            screen.blit(start_text, text_rect)

        pygame.display.flip()
        clock.tick(FPS)


def show_lobby_screen(client_interface):
    try:
        background_img = pygame.image.load('assets/bg/choose_player.png').convert()
        background_img = pygame.transform.scale(background_img, (WIDTH, HEIGHT))
    except pygame.error as e:
        print(f"Error memuat background pilih karakter: {e}")
        background_img = None
        
    error_message, cooldown, my_pid = "", 0, None
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and cooldown <= 0 and not my_pid:
                color = "black" if event.key == pygame.K_b else "white" if event.key == pygame.K_w else None
                if color:
                    response = client_interface.register_player(color)
                    if response and response['status'] == 'OK':
                        my_pid, error_message = response['player_id'], ""
                    else:
                        error_message, cooldown = response.get('message', 'Failed'), 120

        if background_img:
            screen.blit(background_img, (0, 0))
        else:
            screen.fill(BLACK)
        
        state = client_interface.get_game_state()

        if state['status'] != 'OK':
            err_text = font_medium.render(state['message'], True, RED)
            screen.blit(err_text, err_text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        else:
            players = state.get('players', {})
            b_taken = any(p['color_type'] == 'black' for p in players.values())
            w_taken = any(p['color_type'] == 'white' for p in players.values())
            
            b_text = font_medium.render("Press [B] for DOG", True, GREY if b_taken else WHITE)
            w_text = font_medium.render("Press [W] for CAT", True, GREY if w_taken else WHITE)
            
            if my_pid:
                wait_text = font_medium.render("Waiting for the opponent...", True, GREEN)
                screen.blit(wait_text, wait_text.get_rect(center=(WIDTH // 2, HEIGHT // 3.5)))
            else:
                screen.blit(b_text, b_text.get_rect(center=(WIDTH // 2, HEIGHT - 120)))
                screen.blit(w_text, w_text.get_rect(center=(WIDTH // 2, HEIGHT - 80)))

            if error_message:
                err_text = font_small.render(error_message, True, RED)
                screen.blit(err_text, err_text.get_rect(center=(WIDTH // 2, HEIGHT - 40)))
                
            if b_taken and w_taken:
                pygame.display.flip(); time.sleep(1)
                final_state = client_interface.get_game_state()
                my_data = next(((pid, p['color_type']) for pid, p in final_state['players'].items() if pid == my_pid), None)
                if my_data: return my_data
                all_ids = list(final_state['players'].keys())
                other_id = next((pid for pid in all_ids if pid != my_pid), None)
                my_id = other_id if my_pid is None else my_pid
                return my_id, final_state['players'][my_id]['color_type']

        if cooldown > 0: cooldown -= 1
        pygame.display.flip(); clock.tick(FPS)


def main_game_loop():

    try:
        pygame.mixer.music.load('assets/sound/Main_music.mp3')
        pygame.mixer.music.set_volume(0.3) 
        pygame.mixer.music.play(loops=-1)
    except pygame.error as e:
        print(f"Peringatan: Tidak bisa memuat file musik latar. Error: {e}")

    show_start_screen()
    client_interface = ClientInterface()
    player_id, player_color = show_lobby_screen(client_interface)
    local_player = PlayerCharacter(player_id, is_local_player=True, initial_color_choice=player_color)
    other_players, wall_objects, gem_objects, hazard_objects = {}, {}, {}, {}
    exit_object, images_b64, match_ended, match_win_status, last_stage = None, {}, False, "", 0
    current_bg_image = None
    stage_win_sound_played = False

    try:
        dog_treat_img = pygame.image.load('assets/ingame_interaction/dogtreats.png').convert_alpha()
        cat_treat_img = pygame.image.load('assets/ingame_interaction/cattreats.png').convert_alpha()
        exit_cave_img = pygame.image.load('assets/ingame_interaction/cavehome.png').convert_alpha()
    except pygame.error as e:
        print(f"Peringatan: Tidak bisa memuat gambar treats/exit. Error: {e}")
        dog_treat_img = None
        cat_treat_img = None
        exit_cave_img = None

    end_screen_images = {}
    try:
        dog_wins_img = pygame.image.load('assets/bg/dogwins.png').convert()
        cat_wins_img = pygame.image.load('assets/bg/catwins.png').convert()
        end_screen_images['player_black'] = pygame.transform.scale(dog_wins_img, (WIDTH, HEIGHT))
        end_screen_images['player_white'] = pygame.transform.scale(cat_wins_img, (WIDTH, HEIGHT))
    except pygame.error as e:
        print(f"Peringatan: Gagal memuat gambar layar akhir. Error: {e}")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            
        state = client_interface.get_game_state()
        if not (state and state['status'] == 'OK'):
            # time.sleep(1); 
            continue
            
        game_info = state['game_info']
        if game_info['match_winner'] and not match_ended:
            pygame.mixer.music.fadeout(2000)

            if local_player.winmatch:
                local_player.winmatch.play()
            match_ended = True

        if match_ended:
            winner_id = game_info.get('match_winner')
            end_image = end_screen_images.get(winner_id)
            if end_image:
                screen.blit(end_image, (0,0))
            
            pygame.display.flip()

            keys = pygame.key.get_pressed()
            if keys[pygame.K_q]: running = False
            if keys[pygame.K_r]:
                client_interface.reset_game() 
                time.sleep(0.5)
                stage_win_sound_played = False
                main_game_loop()
                return
        else:
            current_stage = game_info['current_stage']
            if current_stage != last_stage:
                logging.info(f"--- Entering Stage {current_stage} ---")
                gem_objects.clear(); hazard_objects.clear(); wall_objects.clear(); exit_object = None
                last_stage = current_stage
                stage_win_sound_played = False
                try:
                    filepath = f'assets/bg/background {current_stage}.png'
                    logging.info(f"Loading background: {filepath}")
                    loaded_image = pygame.image.load(filepath).convert()
                    current_bg_image = pygame.transform.scale(loaded_image, (WIDTH, HEIGHT))
                except Exception as e:
                    logging.error(f"Error loading background for stage {current_stage}: {e}")
                    current_bg_image = None
            
            p_ids = set(state['players'].keys())
            for p_id, p_data in state['players'].items():
                if p_id == local_player.id: local_player.update_from_server(p_data)
                else:
                    if p_id not in other_players: other_players[p_id] = PlayerCharacter(p_id, initial_color_choice=p_data['color_type'])
                    other_players[p_id].update_from_server(p_data)
            for p_id in list(other_players.keys()):
                if p_id not in p_ids: del other_players[p_id]
            
            if not images_b64: images_b64 = state.get('images', {})
            
            if not wall_objects and state.get('walls'):
                for w in state['walls']: wall_objects[w['id']] = Wall(w['id'], w['x'], w['y'], w['width'], w['height'], images_b64.get('wall'))
            if not hazard_objects and state.get('hazards'):
                for h in state['hazards']: hazard_objects[h['id']] = Hazard(h['id'], h['x'], h['y'], h['type'], h['width'], h['height'], images_b64.get(f"{h['type']}_hazard"))
            
            g_ids = {g['id'] for g in state['gems']}
            for g_id in list(gem_objects.keys()):
                if g_id not in g_ids: del gem_objects[g_id]
            for g in state['gems']:
                if g['id'] not in gem_objects:
                    new_gem = Gem(g['id'], g['x'], g['y'], g['type'], images_b64.get(f"{g['type']}_gem"))
        
                    if new_gem.gem_type == 'black' and dog_treat_img:
                        new_gem.image = pygame.transform.scale(dog_treat_img, GEM_SIZE)
                    elif new_gem.gem_type == 'white' and cat_treat_img:
                        new_gem.image = pygame.transform.scale(cat_treat_img, GEM_SIZE)
                    
                    gem_objects[g['id']] = new_gem
            
            if not exit_object and state.get('exit_area'):
                e = state['exit_area']
                exit_object = ExitArea(e['x'], e['y'], e['width'], e['height'], images_b64.get('exit'))
                if exit_cave_img:
                    exit_object.image = pygame.transform.scale(exit_cave_img, (e['width'], e['height']))
            
            if game_info['stage_winner'] and not stage_win_sound_played:
                local_player.Stagewin.play()
                stage_win_sound_played = True

            if not game_info['stage_winner']:
                keys = pygame.key.get_pressed()
                local_player.move(keys, list(wall_objects.values()))
                if local_player.lives > 0:
                    for g_id, gem in list(gem_objects.items()):
                        if local_player.rect.colliderect(gem.rect) and gem.gem_type == local_player.color_type:
                            client_interface.collect_gem(local_player.id, g_id)
                            if local_player.get_gem_sound:
                                local_player.get_gem_sound.play()
                            # del gem_objects[g_id]
                            break
                    for h_id, hazard in hazard_objects.items():
                        if local_player.rect.colliderect(hazard.rect) and hazard.hazard_type != local_player.color_type:
                            client_interface.check_hazard_collision(local_player.id, h_id)
                            break
                    if exit_object and local_player.rect.colliderect(exit_object.rect) and not local_player.at_exit:
                        client_interface.player_at_exit(local_player.id)


            local_player.update_animation()
            for p in other_players.values(): p.update() 

            if current_bg_image:
                screen.blit(current_bg_image, (0, 0))
            else:
                screen.fill(BLACK)

            for w in wall_objects.values(): w.draw(screen)
            for h in hazard_objects.values(): h.draw(screen)
            for g in gem_objects.values(): g.draw(screen)
            if exit_object: exit_object.draw(screen)
            local_player.draw(screen)
            for p in other_players.values(): p.draw(screen)
            
            scores = game_info['scores']
            score_text = font_ingame.render(f"Skor: Dog {scores['player_black']} - Cat {scores['player_white']}", True, WHITE)
            screen.blit(score_text, (10, 10))
            
            required_gems_map = game_info.get('required_gems', {})
            player_color_type = local_player.color_type
            if player_color_type in required_gems_map:
                collected = local_player.gems_collected
                required = required_gems_map[player_color_type]
                gem_status_text = font_ingame.render(f"Treats: {collected}/{required}", True, WHITE)
                screen.blit(gem_status_text, (10, 40))

            lives_text = font_ingame.render(f"Lives: {local_player.lives}", True, RED)
            screen.blit(lives_text, (10, 70))

            stage_text = font_ingame.render(f"Stage: {game_info['current_stage']}/{game_info['total_stages']}", True, WHITE)
            screen.blit(stage_text, (WIDTH - stage_text.get_width() - 10, 10))
            elapsed_time = game_info['elapsed_time']
            mins, secs = int(elapsed_time // 60), int(elapsed_time % 60)
            stopwatch_text = font_small.render(f"{mins:02d}:{secs:02d}", True, WHITE)
            screen.blit(stopwatch_text, (WIDTH // 2 - stopwatch_text.get_width() // 2, 10))
            
            if game_info['stage_winner']:
                overlay = pygame.Surface((WIDTH, HEIGHT))
                overlay.set_alpha(150)  
                overlay.fill((0, 0, 0))  

                winner_is_dog = "black" in game_info['stage_winner']
                screen.blit(overlay, (0, 0))
                image_path = "assets/bg/dog_win_stage.png" if winner_is_dog else "assets/bg/cat_win_stage.png"
                win_image = pygame.image.load(image_path).convert_alpha()
                
                image_width, image_height = win_image.get_width(), win_image.get_height()
                win_image = pygame.transform.smoothscale(win_image, (image_width * 0.8 , image_height * 0.8))
                
                screen.blit(win_image, win_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
        
        pygame.display.flip()
        clock.tick(FPS)
        
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    try:
        main_game_loop()
    except Exception as e:
        print("\n!!! TERJADI ERROR PADA APLIKASI CLIENT !!!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\Press Enter untuk keluar...")
        pygame.quit()
        sys.exit()
