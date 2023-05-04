#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This is the server of the project. it will be used to talk to the database and execute SQL

from server_sql_connection import SqlServerConnection
from typing import Callable

import socket  # used to run the socket server
import select  # used to manage cuncurent connections to the server socket
import pickle  # parser that is used when accept and send any python class
import _thread  # used to create multiple threads (in my case allow many players to play)
import uuid  # used to generate a random ID using uuid()
import os  # used to get random bytes for the salt
import hashlib  # used to encrypt the password in the database
import signal  # used to handle keyboard interrupts
import sys  # used to exit the program
import random  # used to generate random numbers


class SocketServer(socket.socket):

    def __init__(self) -> None:
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        """
        - socket.AF_INET is saying our socket host's IP is going to be a IPv4 (Internet Protocol version 4)
        - socket.SOCK_STREAM is saying that the port that the socket will be using is a TCP (Transmission Control Protocol)
        """
        # Gets the current host, internal network. replace with ("", PORT) for external network
        socket_host_data = (socket.gethostname(), 4201)
        # Binds the socket server to the current host name and listens to active connections
        self.bind(socket_host_data)
        print(f"Server started on Host: {socket_host_data[0]} , Port: {socket_host_data[1]}")

        # Set max connection to 6
        self.listen(6)
        self.sockets_list: list[socket.socket] = [self]

        # This SET will keep track of which client/s what is waiting to join a game
        self.waiting_queue: set[socket.socket] = set()
        # This will keep track of all on going games
        self.ongoing_games: dict[uuid.UUID, dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] |
                                                 int | list[socket.socket] | tuple[str, int, int, int]]] = {}
        # This will store all connected users
        self.clients: dict[socket.socket, tuple[str, int, int, int]] = {}

        # Define the size of the length of the header
        self.HEADERSIZE = 10
        # Connect to the database
        self.DB = SqlServerConnection()

        # Actions that authenticated users can call
        self.actions: dict[str, Callable[..., object]] = {
            "[JOIN GAME]": self.join_game,
            "[CANCEL GAME]": self.cancel_game,
            "[TAKE TURN]": self.take_turn,
            "[GET ALL PLAYER STATS]": self.get_all_player_stats
        }

        self._action_handler()

    def _action_handler(self) -> None:
        while True:
            # Defines our read, write and errored listed sockets
            read_sockets, _write, error_sockets = select.select(self.sockets_list, [], self.sockets_list)

            # Report any errors
            for error_socket in error_sockets:
                print(f"Error: {socket.socket(error_socket).getpeername()} has left the server")

            for user_socket in read_sockets:
                if user_socket == self:
                    """
                    These will be the client sockets trying to connect to the server socket.
                    So in this block i will be authenticating client sockets.
                    """
                    # Accept connections from server, this is so i can read the package
                    client_socket, client_address = self.accept()
                    print(client_socket, client_address)

                    # Handle the incomming document action
                    client_action_document = self.recv_doc_manager(client_socket)

                    if client_action_document is False or type(client_action_document) is not dict:
                        # Disconnection, left the sockect
                        continue

                    # HANDLE UNAUTHENTICATED USERS
                    if client_action_document["action"] == '[USER LOGIN]':  # Login attempt
                        """
                        Authenticate the user, this should return the user data in the database
                        if the username and password is correct. 
                        """
                        # Get user data from database
                        data: tuple[str, str] = client_action_document["data"]  # type: ignore
                        user = self.login_manager(data)

                        if user["result"] is False or type(user["data"]) is not tuple:
                            # Client failed to authenticate
                            # user[data] is the error message
                            client_socket.send(self.pkg_doc_manager("[USER LOGIN - FAIL]", user["data"]))
                            continue

                        # Login user successful
                        # user[data] is the users account data
                        client_socket.send(self.pkg_doc_manager("[USER LOGIN - SUCCESS]", user["data"]))
                        self.sockets_list.append(client_socket)  # Accept future request from this socket.
                        self.clients[client_socket] = user["data"]  # keep track of who is logged in.
                        print(
                            f'Accepted new connection from {client_address[0]}:{client_address[1]}, action_type: {client_action_document["action"]}, Username: {user["data"][0]}'
                        )
                        continue

                    if client_action_document["action"] == '[USER REGISTER]':  # Register attempt
                        # Register the user in the db
                        data: tuple[str, str] = client_action_document["data"]  # type: ignore
                        create_account_status = self.registration_manager(data)

                        if create_account_status["result"] is False:
                            # Something went wrong whilst creating the user account on the database
                            client_socket.send(
                                self.pkg_doc_manager("[USER REGISTER - FAIL]", create_account_status["msg"]))
                            continue

                        # Tell the client that they have successfully created an account tn the database
                        client_socket.send(
                            self.pkg_doc_manager("[USER REGISTER - SUCCESS]", create_account_status["msg"]))
                        print('Created new account from {}:{}, action_type: {}'.format(
                            *client_address, client_action_document["action"]))
                        continue

                else:
                    """
                    At this point the connected client socket has already been authenticated
                    """
                    client_action_document = self.recv_doc_manager(user_socket)

                    if client_action_document is False or client_action_document is None or type(
                            client_action_document) is bool:
                        # Disconnection, left the sockect
                        print(f'Closed connection from User:{self.clients[user_socket][0]}')
                        self.sockets_list.remove(user_socket)
                        del self.clients[user_socket]
                        continue

                    if type(client_action_document["action"]) is not str:
                        breakpoint()
                        continue

                    # Handle any other action being passed to the server
                    print(f"{client_action_document['action']}: UserName: {self.clients[user_socket][0]}")
                    action = self.actions[client_action_document["action"]]
                    if action is False:
                        # This happends when the action type sent to the server isnt known
                        user_socket.send(
                            self.pkg_doc_manager("[ERROR - ACTION]",
                                                 f"Unregistered action type {client_action_document['action']}"))
                        continue

                    # Start a new thread so that the action that is being sent doesn't hault reading other client messages
                    _thread.start_new_thread(action, (user_socket, client_action_document["data"]))
                    continue

    def recv_doc_manager(
        self, client_socket: socket.socket
    ) -> dict[str, str | tuple[str, int, int, int] | list[tuple[str, int, int, int]] |
              dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] | int | list[socket.socket]] |
              bool] | None | bool:
        try:
            # Get the header of the package.
            message_header = client_socket.recv(self.HEADERSIZE)

            # This occures if the user disconnects or sends back no data.
            if not len(message_header):
                return False
            # Remove the extra spaces that we added in the HEADERSIZE and cast the tring into a integer.
            document_length = int(message_header.decode('utf-8').strip())
            # Get and store the actual action document that was sent to the server.
            doc = client_socket.recv(document_length)

            # Turn bytes into a python object.
            return pickle.loads(doc)
        except BlockingIOError:
            return
        except:
            return False

    def pkg_doc_manager(
        self, action: str, document: bool | str | tuple[str, int, int, int] | list[tuple[str, int, int, int]] |
        dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] | int | list[socket.socket] |
             tuple[str, int, int, int]]
    ) -> bytes:
        """
        Format the document that the server wants to send to the client socket to bytes.
        This will be done by pickling the doc object and adding the heading (length of
        the object in bytes).

        action  = The action type that is being packaged up.
        document = The data attached to the action.
        """
        # Check if the action and its data are not left empty.
        if not action:
            raise ValueError('You can not send an empty action type')
        if not document:
            raise ValueError('You can not send an empty document')
        doc = {"action": action, "data": document}

        # This turns the python class into bytes that can be sent to the server.
        pkged_doc = pickle.dumps(doc)

        # The header will contain the length of the pkged_doc in bytes.
        pkged_doc_with_header = bytes(f"{len(pkged_doc):<{self.HEADERSIZE}}", 'utf-8') + pkged_doc

        # This can be sent over the socket.
        return pkged_doc_with_header

    def registration_manager(self, user_credentials: tuple[str, str]) -> dict[str, bool | str]:
        """
        Register the username on the database only if the username isnt taken

        user_credentials = ("username", "password")
        """
        try:
            c = self.DB.connection.cursor()
            c.execute("SELECT username FROM users WHERE username = :username", {"username": user_credentials[0]})
            user_credentials_from_DB: tuple[str] | None = c.fetchone()

            # Checks if there already a player with that username
            if user_credentials_from_DB is None:
                # Create new user WITH USERNAME AND PASSWORD because there is no user with the desired username

                # Generate salt and hash the password
                salt = os.urandom(24)
                hashed_password = hashlib.pbkdf2_hmac('sha512', user_credentials[1].encode('utf-8'), salt, 100000)

                c.execute("INSERT INTO  users (username, password, salt) VALUES (?, ?, ?)",
                          (user_credentials[0], hashed_password.hex(), salt.hex()))
                self.DB.connection.commit()
                return {"result": True, "msg": "Account was created successfully."}
            else:
                return {"result": False, "msg": "Username already exists."}
        except BaseException as e:
            print(e)
            return {"result": False, "msg": "Error when creating client's account."}

    def login_manager(self, user_credentials: tuple[str, str]) -> dict[str, bool | str | tuple[str, int, int, int]]:
        """
        Handle the authentication of the client.
        This function will query the database for the desired username and compare hashed passwords
        if they match, this will return the desired userdata <minus the hashed password>
        """
        try:
            c = self.DB.connection.cursor()
            c.execute("SELECT username, password, salt FROM users WHERE username = :username",
                      {"username": user_credentials[0]})
            user_credentials_from_DB: tuple[str, str, str] | None = c.fetchone()

            if user_credentials_from_DB is None:
                # There is no accounts with the passed in username, return error
                return {"result": False, "data": f"No user found with the username: {(user_credentials[0])}"}

            # Check if the user is already logged in
            if list(filter(lambda x: user_credentials[0] in x, list(self.clients.values()))):
                return {"result": False, "data": "User is already logged in."}

            # Hash the password with the salt from the database
            hashed_password = hashlib.pbkdf2_hmac('sha512', user_credentials[1].encode('utf-8'),
                                                  bytes.fromhex(user_credentials_from_DB[2]), 100000)
            # Check if hashed passwords match
            if user_credentials_from_DB == (user_credentials[0], hashed_password.hex(), user_credentials_from_DB[2]):
                c.execute("SELECT username, wins, loses, games_played FROM users WHERE username = ?",
                          (user_credentials[0],))
                user_data: tuple[str, int, int, int] = c.fetchone()

                return {"result": True, "data": user_data}  # return user data
            else:
                return {"result": False, "data": "Incorrect password"}  # return error
        except BaseException as e:
            print(e)
            return {"result": False, "data": "Error when authenticating client's account."}

    def join_game(self, client: socket.socket, data: tuple[str, tuple[int, int]]) -> None:
        """
        Adds the client to the waiting_queue
         if the client is the first one in the queue they will become host
          - the host will create the game session
        else they will get told to join a game by the server from the host request

        <difficulty>  the server can't send the socket class
        """
        username, board_size = data
        try:
            # Add user to game queue - session
            self.waiting_queue.add(client)
            host = False
            while (len(self.waiting_queue) < 2):  # This client is the only player in the game queue
                host = True  # This make setting up the game easier as one client will be responsible for setting it up
                if client in self.waiting_queue:  # If the client is still waiting in the for a game lobby
                    client.send(self.pkg_doc_manager("[JOIN GAME - WAITING]", username))
                else:
                    # "Client left the queue"
                    return

            if host:
                gameID = uuid.uuid1()
                Game_Board_Data: dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] | int |
                                      list[socket.socket]] = {
                                          'id': gameID,
                                          'player_data': [],
                                          'board': [],
                                          'player_turn': 1,
                                      }
                # Create the game board
                for _ in range(board_size[0]):
                    Game_Board_Data['board'].append([0] * board_size[1])
                # Shuffle the board
                self.shuffle_board(Game_Board_Data['board'])
                # Get the players
                players: list[socket.socket] = []
                for _ in range(2):  # 2 player game
                    player_clinet = self.waiting_queue.pop()
                    players.append(player_clinet)
                    # Let the clinet know that they are getting connected to a game.
                    # The socket client and their user_data
                    # If Game_Board_Data['player_data'] is not list[tuple[str, int, int, int]], then continue
                    Game_Board_Data['player_data'].append(self.clients[player_clinet])  # type: ignore
                for _, client in enumerate(players):
                    client.send(self.pkg_doc_manager("[JOIN GAME - SUCCESS]", Game_Board_Data))
                Game_Board_Data['clients'] = players

                # Add the Game_Board_Data to the ongoing games data record
                self.ongoing_games[gameID] = Game_Board_Data
            return
        except:
            self.waiting_queue.remove(client)
            return

    def cancel_game(self, client: socket.socket, username: str) -> None:
        """
        Remove client from waiting queue
        """
        if client in self.waiting_queue:
            self.waiting_queue.remove(client)
            client.send(self.pkg_doc_manager("[CANCEL GAME - SUCCESS]", "Cancelled"))
        else:
            client.send(self.pkg_doc_manager("[CANCEL GAME - FAIL]", "Not waiting for a game"))
        return

    def take_turn(self, client: socket.socket,
                  data: dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] | int |
                             list[socket.socket] | tuple[str, int, int, int]]):
        """
        - The clinet will pass the game id that they want to updata
        - Then the server will send both clients the updated board

        <difficulty>  the server can't send the socket class so i have to create a clone of the data that the client sent
        """
        try:
            # Update game board
            self.ongoing_games[data["id"]]["board"] = data["board"]
            """
            Update player turn
            example: 
                player 1 starts:
                1 % 2 = 1, + 1 = 2 turn
                2 % 2 = 0, + 1 = 1 turn 
            """
            data["player_turn"] = (data["player_turn"] % 2) + 1
            self.ongoing_games[data["id"]]["player_turn"] = data["player_turn"]

            # Check if any players won
            is_winner = self.check_if_winner(self.ongoing_games[data["id"]]["board"])  # type: ignore

            if is_winner != 0:
                # Notifiy players that the game has a winner
                data["winner"] = is_winner
                # Go through all players in the current game
                clients: list[socket.socket] = self.ongoing_games[data["id"]]["clients"]  # type: ignore
                for i, client in enumerate(clients):
                    # Update database
                    if i + 1 == data["winner"]:
                        # This client won the game
                        self.update_user_data_after_game(client, True)
                    else:
                        # This client lost or drew
                        self.update_user_data_after_game(client)
                    data["updated_user_data"] = self.clients[client]
                    client.send(self.pkg_doc_manager("[GAME - END]", data))

                # Close game session
                del self.ongoing_games[data["id"]]
                return

            clients: list[socket.socket] = self.ongoing_games[data["id"]]["clients"]  # type: ignore
            for client in clients:
                client.send(self.pkg_doc_manager("[GAME - TURN]", data))
            return
        except:
            # Close game session
            if type(data["id"]) is uuid.UUID:
                del self.ongoing_games[data["id"]]
            raise

    def check_if_winner(self, board: list[list[int]]) -> int:
        """
        checks if there is a winning state
        """

        if all(all(item % 2 == 0 for item in items) for items in board):
            return 1
        elif all(all(item % 2 == 1 for item in items) for items in board):
            return 2
        else:
            return 0  # no end state (the game is still playable - ongoing)

    def init_coeff_matrix(self, x: int, y: int) -> list[list[int]]:
        matrix = [[0 for _ in range(x * y + 1)] for _ in range(x * y)]
        for i in range(x):
            for j in range(y):
                k = i * y + j
                matrix[k][k] = 1
                if i > 0:
                    matrix[(i - 1) * y + j][k] = 1
                if i < x - 1:
                    matrix[(i + 1) * y + j][k] = 1
                if j > 0:
                    matrix[i * y + j - 1][k] = 1
                if j < y - 1:
                    matrix[i * y + j + 1][k] = 1
        return matrix

    def solve(self, matrix: list[list[int]]) -> list[list[list[int]]]:
        cells = len(matrix) * len(matrix[0])
        coeff_rank, matrix_rank = 0, 0
        coeff_matrix = self.init_coeff_matrix(len(matrix), len(matrix[0]))
        # Add our problem to coefficient matrix
        for i in range(len(matrix)):
            for j in range(len(matrix[i])):
                coeff_matrix[i * len(matrix[i]) + j][cells] = matrix[i][j] & 1  # Convert to binary

        # Conversion of augmented matrix to ladder matrix
        for i, y in zip(range(cells), range(cells)):
            x = i
            for j in range(i + 1, cells):
                if coeff_matrix[j][i] > coeff_matrix[x][i]:
                    x = j
            if x - i:  # Exchange matrix row data
                for k in range(y, cells + 1):
                    coeff_matrix[i][k] ^= coeff_matrix[x][k]
                    coeff_matrix[x][k] ^= coeff_matrix[i][k]
                    coeff_matrix[i][k] ^= coeff_matrix[x][k]
            if coeff_matrix[i][y] == 0:
                i -= 1
                continue
            # Elimination
            for j in range(i + 1, cells):
                if coeff_matrix[j][y]:
                    for k in range(y, cells + 1):
                        coeff_matrix[j][k] ^= coeff_matrix[i][k]

        # Computation of Rank of Coefficient Matrix and Rank of Extended Matrix
        solution = []
        for i in range(cells):
            rank1, rank2 = 0, 0
            for j in range(cells + 1):
                if j < cells:
                    rank1 |= coeff_matrix[i][j]
                rank2 |= coeff_matrix[i][j]
            coeff_rank += rank1
            matrix_rank += rank2

        # Enumeration and Replacement Solution
        if coeff_rank >= matrix_rank:
            temp = [0 for _ in range(cells)]
            for i in range(1 << (cells - coeff_rank), 0, -1):
                for j in range(cells - 1, coeff_rank, -1):
                    coeff_matrix[j - 1][cells] += coeff_matrix[j][cells] >> 1
                    coeff_matrix[j][cells] &= 1
                for j in range(cells):
                    temp[j] = coeff_matrix[j][cells]
                for j in range(cells - 1, -1, -1):
                    for k in range(j - 1, -1, -1):
                        if coeff_matrix[k][j]:
                            temp[k] ^= temp[j]

                temp2d = [[0 for _ in range(len(matrix[0]))] for _ in range(len(matrix))]
                for j in range(len(temp2d)):
                    for k in range(len(temp2d[j])):
                        temp2d[j][k] = temp[j * len(temp2d[j]) + k]
                solution.append(temp2d)
                coeff_matrix[cells - 1][cells] += 1
        return solution

    def shuffle_board(self, board: list[list[int]]) -> list[list[int]]:
        # Randomize game board
        for row in board:
            for i in range(len(row)):
                row[i] = random.randint(1, 2)
        # Check if the board is solvable
        solutions = self.solve(board)
        if len(solutions) == 0:
            return self.shuffle_board(board)
        elif all(all(item % 2 == 0 for item in items) for items in board):
            return self.shuffle_board(board)
        elif all(all(item % 2 == 1 for item in items) for items in board):
            return self.shuffle_board(board)
        return board

    def update_user_data_after_game(self, client: socket.socket, won: bool = False) -> None:
        """
        Update the players data on the server and the database after a game 
        """
        try:
            c = self.DB.connection.cursor()
            if won:
                c.execute("UPDATE users SET wins = wins+1, games_played=games_played+1 WHERE username = :username",
                          {"username": self.clients[client][0]})
                self.DB.connection.commit()
                print(self.clients[client][0], "won")
            else:
                c.execute("UPDATE users SET loses=loses+1, games_played=games_played+1 WHERE username = :username",
                          {"username": self.clients[client][0]})
                self.DB.connection.commit()
                print(self.clients[client][0], "lost")

            c.execute("SELECT username, wins, loses, games_played FROM users WHERE username = ?",
                      (self.clients[client][0],))
            user_credentials_from_DB: tuple[str, int, int, int] = c.fetchone()

            # Update client's data on the server
            self.clients[client] = user_credentials_from_DB
        except:
            raise

    def get_all_player_stats(self, client: socket.socket, username: str) -> None:
        """
        Query the database for all users statistics and return them in an array
        """
        try:
            c = self.DB.connection.cursor()
            c.execute("SELECT username, wins, loses, games_played FROM users")
            user_credentials_from_DB: list[tuple[str, int, int, int]] = c.fetchall()

            client.send(self.pkg_doc_manager("[GET ALL PLAYER STATS - SUCCESS]", user_credentials_from_DB))
        except:
            client.send(
                self.pkg_doc_manager("[GET ALL PLAYER STATS - FAIL]", "Error whilst getting all player statistics"))


def signal_handler(sig, frame):
    """
    This function will be called when the program is terminated
    """
    print("Closing server")
    sys.exit(0)


if __name__ == "__main__":  # Only run this code if this python file is the root file execution
    signal.signal(signal.SIGINT, signal_handler)
    server = SocketServer()
