#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This is the client of the project. It will be used to talk to the server.

import socket  # used to create the client socket connection with the server socket.
import pickle  # parser that is used to accept and send any python class.
import uuid  # used to generate a unique id for the game
import tkinter as tk  # used to get datatype

# Set up the socket


class ClientServerSocket(socket.socket):
    # Default the host will be "socket.gethostname()" which in the current computer.
    # socket_host_data will have to be passed if the server isnt running on the current computer.
    def __init__(self, socket_host_data=(socket.gethostname(), 4201)) -> None:
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        """"
        - socket.AF_INET is saying our socket host's IP is going to be a IPv4 (Internet Protical version 4)
        - socket.SOCK_STREAM is saying that the port that the socket will be using is a TCP (Transmission Control Protocol)
        """
        try:
            self.connect(socket_host_data)
        except BaseException as e:
            print(e)
            raise ConnectionError(
                f"Could not connect to the HostName: {socket_host_data[0]}, Port: {socket_host_data[1]} - It may not exist or be down."
            )

        # Define the size of the length of the header needs to be the same on the server
        self.HEADERSIZE = 10

        # Is the user successfully authenticated?
        self.is_auth: bool = False
        # Is client waitig to join a game?
        self.is_waiting: bool = False
        # Is client currently in a game?
        self.is_in_game: bool = False

        self.user_data: tuple[str, int, int, int]
        self.game_data: dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] | int |
                             list[socket.socket] | tuple[str, int, int, int]]
        # Leaderboard
        self.leaderboard: list[tuple[str, int, int, int]]

        # if self.isAuth is False:
        #    raise(BaseException("Password Or Username Was Incorrect"))

    async def recv_doc_manager(self):
        try:
            # get the header size
            message_header = self.recv(self.HEADERSIZE)

            # this occures if the user disconnects or sends back no data
            if not len(message_header):
                return False
            # this line will remove the extra spaces that we added in the HEADERSIZE and cast the tring into a integer
            document_length = int(message_header.decode('utf-8').strip())
            # this will store the actual document that was sent to the server
            doc = self.recv(document_length)

            return pickle.loads(doc)
        except BlockingIOError:
            return
        except:
            return False

    def pkg_doc_manager(self, action, document):
        """
        Handle the the document that the user wants to send to the socket server
        This will be done by pickling the doc object and adding the heading (length of
        the object in bytes)

        action  = The action type that is being packaged up.
        document = The data attached to the action
        """
        if not action:
            raise (BaseException("You can't send an empty action type"))
        if not document:
            raise (BaseException("You can't send an empty document"))

        doc = {"action": action, "data": document}

        # this turns the python class into bytes that can be sent to the server
        pkged_doc = pickle.dumps(doc)

        # The header will contain the length of the pkged_document bytes
        pkged_doc_with_header = bytes(f"{len(pkged_doc):<{self.HEADERSIZE}}", 'utf-8') + pkged_doc

        return pkged_doc_with_header

    #
    # This will get passed in a username and passwor -> the socket server will validate the user's Credential
    # Returns the user data if its valid, else it will return null
    #

    async def login(self, user_credentials: tuple[str, str]) -> bool | str | None:
        """
        Attempt to authenitcate the client with a username and password on the socket client 
        """
        # Checks if the client isn't already authenticated
        if self.is_auth is False:
            packaged_auth_login_document = self.pkg_doc_manager("[USER LOGIN]", user_credentials)
            self.send(packaged_auth_login_document)
            results: bool | dict[str, str | tuple[str, int, int, int]] | None = await self.recv_doc_manager()

            # nothing was sent back, something broke on the server (disconnected)
            if results is None or results is False:
                return False

            print(results["action"])
            if results["action"] == "[USER LOGIN - FAIL]":
                # user failed to authenticate client
                return results["data"]
            # successfully authenticated client's account
            self.user_data = results["data"]
            self.is_auth = True
            return True

    async def register(self, user_credentials: tuple[str, str]) -> bool | str | None:
        '''
        Register the user on the socket server
        '''
        # Checks if the client isn't already authenticated
        if self.is_auth is False:
            packaged_auth_register_document = self.pkg_doc_manager("[USER REGISTER]", user_credentials)
            self.send(packaged_auth_register_document)
            results: bool | dict[str, str] | None = await self.recv_doc_manager()

            # nothing was sent back, something broke on the server (disconnected)
            if results is None or results is False:
                return "Error: no connection to the socket"

            if results["action"] == "[USER REGISTER - FAIL]":
                # failded to create user account client
                return results["data"]

            # successfully created user account
            return results["data"]

    async def join_game(self, board_size: tuple[int, int]):
        # Checks if the client is already authenticated
        if self.is_auth is True and self.is_waiting is False and self.is_in_game is False:
            data: tuple[str, tuple[int, int]] = (self.user_data[0], board_size)
            packaged_join_game_request_document = self.pkg_doc_manager("[JOIN GAME]", data)
            self.send(packaged_join_game_request_document)
            self.is_waiting = True

            results: bool | dict[str, str | dict[str, uuid.UUID | list[tuple[str, int, int, int]] | list[list[int]] |
                                                 int | list[socket.socket]]] | None = await self.recv_doc_manager()

            if results is None:  # Nothing was sent back, something broke on the server (disconnected)
                self.is_waiting = False
                return "Error: no connection to the socket"

            if results is False or type(results) is bool:
                return

            while results["action"] == "[JOIN GAME - WAITING]":
                results = await self.recv_doc_manager()
                if results is None:
                    self.is_waiting = False
                    return "Error: no connection to the socket"

            if results["action"] == "[CANCEL GAME - FAIL]":
                # No in the waiting game queue
                return results["data"]

            self.is_waiting = False
            # if  results["action"] == "[JOIN GAME - CANCELLED]":
            #     # Vancelled game
            #     return results["data"]

            # the client is connecting
            if results["action"] == "[JOIN GAME - SUCCESS]":
                # Duccessfully joined a game
                self.is_in_game = True
                self.game_data = results["data"]
                return True

            if results["action"] == "[CANCEL GAME - SUCCESS]":
                # Cancelled game
                self.is_waiting = False
                return results["data"]

    async def cancel_game(self) -> None:
        """
        Leave the game queue
        """
        # Checks if the client is already authenticated
        if self.is_auth is True and self.is_waiting is True and self.is_in_game is False:
            packaged_leave_game_queue_document = self.pkg_doc_manager("[CANCEL GAME]", self.user_data[0])
            self.send(packaged_leave_game_queue_document)

    async def start_game_loop(self, frame: tk.Frame) -> None:
        """
        Listens to any updates from the server 
        """
        try:
            results = await self.recv_doc_manager()

            if results is None:  # Nothing was sent back, something broke on the server (disconnected)
                self.is_waiting = False
                return "Error: no connection to the socket"

            while results["action"] == "[GAME - TURN]":
                self.game_data = results["data"]
                frame.render()
                results = await self.recv_doc_manager()
                if results is None:
                    self.is_in_game = False
                    return "Error: no connection to the socket"

            if results["action"] == "[GAME - END]":
                self.game_data = results["data"]
                self.user_data = self.game_data["updated_user_data"]
                # Game ended
                frame.MSG.set("Player " + str(self.game_data["winner"]) + " has won!")
                frame.render()
                frame.msg_label.grid()
                frame.end_game_btn.grid()
                self.is_in_game = False
                return

        except:
            self.is_in_game = False
            self.game_data = {}
            raise

    def switch_cell(self, matrix: list[list[int]], x: int, y: int) -> list[list[int]]:
        matrix[x][y] += 1
        if x > 0:
            matrix[x - 1][y] += 1
        if x < len(matrix) - 1:
            matrix[x + 1][y] += 1
        if y > 0:
            matrix[x][y - 1] += 1
        if y < len(matrix[0]) - 1:
            matrix[x][y + 1] += 1
        return matrix

    async def take_turn(self, rowCol):
        """
        Make an action on the board by sending the data to the socket server
        """
        # Make sure the player is in a game
        if self.is_auth is True and self.is_in_game is True:

            # Update board
            self.game_data["board"] = self.switch_cell(self.game_data["board"], rowCol[0], rowCol[1])

            # Send the take turn action to the server
            packaged_game_board_action_document = self.pkg_doc_manager("[TAKE TURN]", self.game_data)
            self.send(packaged_game_board_action_document)
        return

    async def get_all_player_stats(self) -> bool | str | None:
        # Make sure the client is authenticated and not in a game
        try:
            if self.is_auth is True and self.is_in_game is False:
                packaged_get_player_all_data_action_document = self.pkg_doc_manager("[GET ALL PLAYER STATS]",
                                                                                    self.user_data[0])
                self.send(packaged_get_player_all_data_action_document)
                results: bool | dict[str, str | tuple[str, int, int, int]] | None = await self.recv_doc_manager()

                # Nothing was sent back, something broke on the server (disconnected)
                if results is None or results is False:
                    return "Error: no connection to the socket"

                if results["action"] == "[GET ALL PLAYER STATS - FAIL]":
                    # Failded to get user statistics
                    self.leaderboard = []
                    return results["data"]

                # Successfully get user statistics
                self.leaderboard = sorted(results["data"], key=lambda tup: tup[1] - tup[2],
                                          reverse=True)  # sort the player data
                return True
        except:
            raise


if __name__ == "__main__":  # Only run this code if this python file is the root file execution
    try:
        s = ClientServerSocket()
        dummy = s.login(("test", "tEst3_14159"))

    except ConnectionError as e:
        print(e)
