import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import CreateJoinRoom from "./CreateJoinRoom";

const BACKEND_URL = "http://localhost:5000";

function App() {
  const [connected, setConnected] = useState(false);
  const [inRoom, setInRoom] = useState(false);
  const [lobbyInfo, setLobbyInfo] = useState(null);
  const lobbyInfoRef = useRef(null);  // Ref to keep latest lobbyInfo
  const [socket, setSocket] = useState(null);
  const [playerHand, setPlayerHand] = useState([]);

  // Keep lobbyInfoRef in sync with lobbyInfo state
  useEffect(() => {
    lobbyInfoRef.current = lobbyInfo;
  }, [lobbyInfo]);

  useEffect(() => {
    const s = io(BACKEND_URL, { transports: ["polling"] });
    setSocket(s);

    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));

    s.on("room_joined", data => {
      console.log("room_joined event received!", data);
      setLobbyInfo(data);
      setInRoom(true);
    });

    s.on("room_update", data => {
      console.log("room_update event received!", data);
      setLobbyInfo(prev => prev ? {
        ...prev,
        players: data.players,
        readyStates: data.readyStates || prev.readyStates
      } : null);
    });

    s.on("deal_hand", data => {
      if (lobbyInfoRef.current && data.username === lobbyInfoRef.current.username) {
        console.log("Received hand cards:", data.hand);
        setPlayerHand(data.hand);
      }
    });

    s.on("game_started", data => {
      alert("Game is starting! (Gameplay coming next)");
      // TODO: transition to gameplay UI
    });

    s.on("error_msg", msg => {
      alert(msg);
    });

    return () => {
      s.disconnect();
    };
  }, []);  // <-- Note the dependency to have latest lobbyInfo

  const handleCreateRoom = ({ username, cardBack, wildCards }) => {
    if (socket) {
      socket.emit("create_room", { username, cardBack, wildCards });
    }
  };

  const handleJoinRoom = ({ username, roomId }) => {
    if (socket) {
      socket.emit("join_room", { username, roomId });
    }
  };

  const toggleReady = () => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username, readyStates } = lobbyInfo;
    const currentlyReady = readyStates ? readyStates[username] : false;
    socket.emit("set_ready", {
      roomId,
      username,
      ready: !currentlyReady
    });
  };

  const startGame = () => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username } = lobbyInfo;
    socket.emit("start_game", { roomId, username });
  };

  if (inRoom && lobbyInfo) {
    const { roomId, username, players, settings, readyStates = {} } = lobbyInfo;
    const isCreator = players[0] === username;
    const allReady = players.every(player => readyStates[player]);

    return (
      <div style={{ textAlign: "center", marginTop: "4rem" }}>
        <h2>Lobby - Room {roomId}</h2>
        <p>Welcome, {username}!</p>
        <p>
          <strong>Card Back:</strong> {settings?.cardBack || "N/A"} <br />
          <strong>Wild Cards Enabled:</strong> {settings?.wildCards ? "Yes" : "No"}
        </p>
        <p>Players in room:</p>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {players.map(player => (
            <li key={player}>
              {player}{" "}
              <span style={{ color: readyStates[player] ? "green" : "gray" }}>
                {readyStates[player] ? "✔️ Ready" : "⏳ Not Ready"}
              </span>
            </li>
          ))}
        </ul>
        <button onClick={toggleReady} style={{ marginRight: 10 }}>
          {readyStates[username] ? "Unready" : "Ready"}
        </button>
        {isCreator && (
          <button disabled={!allReady} onClick={startGame}>
            Start Game
          </button>
        )}

        {/* Player's hand display */}
        <h3>Your hand:</h3>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            marginTop: 10,
          }}
        >
          {playerHand.map(card => (
            <div
              key={card}
              style={{
                border: "1px solid black",
                borderRadius: 4,
                padding: "0.5rem",
                margin: "0.25rem",
                minWidth: 40,
                textAlign: "center",
                backgroundColor: "white",
                userSelect: "none",
              }}
            >
              {card}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ textAlign: "center" }}>Guan Dan Web Game</h1>
      <h3 style={{ textAlign: "center", color: connected ? "green" : "red" }}>
        Socket.IO: {connected ? "Connected" : "Disconnected"}
      </h3>
      <CreateJoinRoom onCreateRoom={handleCreateRoom} onJoinRoom={handleJoinRoom} />
    </div>
  );
}

export default App;
