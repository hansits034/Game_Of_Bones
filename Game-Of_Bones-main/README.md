# Game-Of_Bones 🐕🦴🐈
Game of Bones is a 2-player networked platformer game where a dog and a cat compete across multiple stages. This guide will walk you through setting up and running the game on your local machine.

## Architecture Overview 🏗️
The game operates on a client-server model:

- `game_server_http.py`: The central server that runs the game, listening for clients on port 8889.

- `http_handler.py`: A module used by the server to process incoming HTTP requests from the clients.

- `protocol.py`: The core rulebook for the server. It defines game objects, levels, win/loss conditions, and player interactions.

- `client.py`: The game client that you run to play. It handles rendering graphics and sound with Pygame, capturing player input, and communicating with the server.

## Prerequisites 🛠️
Before you play the game, make sure you have Python installed on your system. You will also need to install a couple of Python libraries.

You can install the required libraries using pip:
```
pip install pygame pillow
```

## 🦴 How To Run Game-Of-Bones 🦴
To play, you must first start the server and then launch two client instances.
### Step 1 : Run the Server
Open a terminal or command prompt, navigate to the project directory, and run the server script.
```
python game_server_http.py
```
You should see a message indicating that the server is running on port 8889. Keep this terminal window open in the background.

### Step 2 : Run the First Client
Open a new terminal or command prompt and run the client script.
```
python client.py
```
A Pygame window will open and displaying the start screen for the first player.

### Step 3 : Run the Second Client
Repeat Step 2 by opening a third terminal window and running the client script again.

### Step 4: Choose Characters and Play
In one client window, press 'B' to choose the Dog or 'W' to choose the Cat. In the other client window, choose the remaining character. The game would be start automatically if both characters are selected.

## How to Play the Game 🎮
### Controls
- Move Left / Right: `A` / `D` or `Left` / `Right` arrow keys.
- Jump: `W` or `Up` arrow key.

### Objective
- **Collect Treats:** Each player must collect their character-specific treats. Fish-bone for the cat and Bone for the Dog.
- **Avoid Hazards:** Touching the hazard that matches the other player's color will cause you to lose a life. If your character is dog, you should avoid the orange hazards. If your character is cat, you should avoid the black hazards.
- **Reach the Exit:** Once you have collected all your required treats, make your way to the exit cave to win the stage.
- **Win the Match:** If you win the majority of the stages (e.g., 2 out of 3), you would be crowned the overall winner.

## 💡 Note on Network Play
By default, the client is configured to connect to a server running on the same machine `127.0.0.1`. If you want to play with someone on a different computer over a local network (LAN), the player running the client needs to edit the `client.py` file.
1. Find the Server's IP Address: The person running `game_server_http.py` needs to find their computer's local IP address.
- On Windows, open Command Prompt and type `ipconfig`.
- On macOS or Linux, open a terminal and type `ifconfig` or `ip a`.
2. Edit the Client File: Open the `client.py` file and change the `server_address` to the server's IP address.
For example, if the server's IP address is `192.168.1.5`, the line should be changed to:
```
self.server_address = ('192.168.1.5', 8889)
```
That change will connect to the other computer on the network.
