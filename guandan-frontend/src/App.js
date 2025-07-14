import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import CreateJoinRoom from "./CreateJoinRoom";

const BACKEND_URL = "http://localhost:5000";

function App() {
  const [connected, setConnected] = useState(false);
  const [inRoom, setInRoom] = useState(false);
  const [lobbyInfo, setLobbyInfo] = useState(null);
  const lobbyInfoRef = useRef(null);
  const [socket, setSocket] = useState(null);
  const [playerHand, setPlayerHand] = useState([]);

  // Gameplay state
  const [currentPlayer, setCurrentPlayer] = useState(null);
  const [currentPlay, setCurrentPlay] = useState(null);
  const [selectedCards, setSelectedCards] = useState([]);

  // Keep lobbyInfoRef in sync with state
  useEffect(() => {
    lobbyInfoRef.current = lobbyInfo;
  }, [lobbyInfo]);

  useEffect(() => {
    const s = io(BACKEND_URL, { transports: ["polling"] });
    setSocket(s);

    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));

    s.on("room_joined", data => {
      setLobbyInfo(data);
      setInRoom(true);
      setCurrentPlayer(null);
      setCurrentPlay(null);
      setSelectedCards([]);
      setPlayerHand([]);
    });

    s.on("room_update", data => {
      setLobbyInfo(prev => prev ? {
        ...prev,
        players: data.players,
        readyStates: data.readyStates || prev.readyStates
      } : null);
    });

    s.on("deal_hand", data => {
      // Only update if this hand belongs to this client
      if (lobbyInfoRef.current && data.username === lobbyInfoRef.current.username) {
        setPlayerHand(data.hand);
      }
    });

    s.on("game_started", data => {
      setCurrentPlayer(data.current_player);
      setCurrentPlay(null);
      setSelectedCards([]);
    });

    s.on("game_update", data => {
      setCurrentPlay(data.current_play);
      setCurrentPlayer(data.current_player);
      if (lobbyInfoRef.current) {
        const username = lobbyInfoRef.current.username;
        if (data.hands && data.hands[username]) {
          setPlayerHand(data.hands[username]);
        }
      }
    });

    s.on("error_msg", msg => {
      alert(msg);
    });

    return () => {
      s.disconnect();
    };
    // Only run once on mount
    // eslint-disable-next-line
  }, []);

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

  const playSelectedCards = () => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username } = lobbyInfo;
    if (selectedCards.length === 0) return;
    socket.emit("play_cards", { roomId, username, cards: selectedCards });
    setSelectedCards([]);
  };

  const passTurn = () => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username } = lobbyInfo;
    socket.emit("pass_turn", { roomId, username });
    setSelectedCards([]);
  };

  // Lobby and gameplay UI
  if (inRoom && lobbyInfo) {
    const { roomId, username, players, settings, readyStates = {} } = lobbyInfo;
    const isCreator = players[0] === username;
    const allReady = players.every(player => readyStates[player]);
    const yourTurn = currentPlayer === username;

    return (
      <div style={{ textAlign: "center", marginTop: "4rem" }}>
        <h2>Room {roomId}</h2>
        <p>Welcome, {username}!</p>
        <p>
          <strong>Card Back:</strong> {settings?.cardBack || "N/A"} <br />
          <strong>Wild Cards Enabled:</strong> {settings?.wildCards ? "Yes" : "No"}
        </p>
        <p>Players:</p>
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
        {/* Pre-game UI */}
        {!currentPlayer && (
          <>
            <button onClick={toggleReady} style={{ marginRight: 10 }}>
              {readyStates[username] ? "Unready" : "Ready"}
            </button>
            {isCreator && (
              <button disabled={!allReady} onClick={startGame}>
                Start Game
              </button>
            )}
          </>
        )}

        {/* Gameplay UI */}
        {currentPlayer && (
          <>
            <h3>Current turn: <span style={{ color: yourTurn ? "#0048ab" : undefined }}>{currentPlayer}</span></h3>
            <div style={{ marginBottom: 10 }}>
              <strong>Last play:</strong>{" "}
              {currentPlay && currentPlay.cards.length > 0
                ? currentPlay.cards.map(card =>
                    <img
                      key={card}
                      src={`${process.env.PUBLIC_URL}/cards/${card}.svg`}
                      alt={card}
                      style={{ width: 40, height: 56, verticalAlign: "middle", marginRight: 3 }}
                    />
                  )
                : <span>Pass</span>}
              {currentPlay ? ` by ${currentPlay.player}` : ""}
            </div>
            <h3>Your hand:</h3>
            <div style={{ display: "flex", justifyContent: "center", flexWrap: "wrap", marginBottom: 10 }}>
              {playerHand.map((card, idx) => {
                const isSelected = selectedCards.includes(card);
                return (
                  <img
                    key={card + idx}
                    src={`${process.env.PUBLIC_URL}/cards/${card}.svg`}
                    alt={card}
                    onClick={() => {
                      if (!isSelected) {
                        setSelectedCards([...selectedCards, card]);
                      } else {
                        setSelectedCards(selectedCards.filter(c => c !== card));
                      }
                    }}
                    style={{
                      width: 50,
                      height: 70,
                      margin: "0.25rem",
                      border: isSelected ? "3px solid #005fff" : "1px solid #222",
                      borderRadius: 6,
                      cursor: "pointer",
                      userSelect: "none",
                      boxShadow: isSelected ? "0 0 8px #005fff88" : undefined,
                      background: "white"
                    }}
                  />
                );
              })}
            </div>
            {yourTurn && (
              <>
                <button
                  disabled={selectedCards.length === 0}
                  onClick={playSelectedCards}
                  style={{ marginRight: 10 }}
                >
                  Play Selected
                </button>
                <button onClick={passTurn}>Pass</button>
              </>
            )}
            {!yourTurn && <p>Waiting for <strong>{currentPlayer}</strong> to play...</p>}
          </>
        )}
      </div>
    );
  }

  // Landing/lobby screen
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
