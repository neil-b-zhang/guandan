import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import CreateJoinRoom from "./CreateJoinRoom";

const BACKEND_URL = "http://localhost:5000";
const CARD_RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2', 'JoB', 'JoR'];

function cardSortKey(card) {
  if (card === "JoB" || card === "JoR") return CARD_RANK_ORDER.indexOf(card);
  const rank = card.startsWith("Jo") ? card : card.slice(0, -1);
  return CARD_RANK_ORDER.indexOf(rank.toUpperCase());
}

function handTypeLabelString(type) {
  switch (type) {
    case 'single': return "Single";
    case 'pair': return "Pair";
    case 'triple': return "Triple";
    case 'full_house': return "Full House";
    case 'straight': return "Straight";
    case 'tube': return "Tube (3 Consecutive Pairs)";
    case 'plate': return "Plate (2 Consecutive Triples)";
    case 'bomb': return "Bomb";
    case 'joker_bomb': return "Joker Bomb";
    default: return type;
  }
}

function App() {
  const [connected, setConnected] = useState(false);
  const [inRoom, setInRoom] = useState(false);
  const [lobbyInfo, setLobbyInfo] = useState(null);
  const lobbyInfoRef = useRef(null);
  const [socket, setSocket] = useState(null);
  const [playerHand, setPlayerHand] = useState([]);
  const [currentPlayer, setCurrentPlayer] = useState(null);
  const [currentPlay, setCurrentPlay] = useState(null);
  const [lastPlayType, setLastPlayType] = useState(null);
  const [selectedCards, setSelectedCards] = useState([]);
  const [canEndRound, setCanEndRound] = useState(false);
  const [passedPlayers, setPassedPlayers] = useState([]);
  const [gameOverInfo, setGameOverInfo] = useState(null);

  useEffect(() => { lobbyInfoRef.current = lobbyInfo; }, [lobbyInfo]);

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
      setLastPlayType(null);
      setSelectedCards([]);
      setPlayerHand([]);
      setCanEndRound(false);
      setPassedPlayers([]);
      setGameOverInfo(null);
    });

    s.on("room_update", data => {
      setLobbyInfo(prev => prev ? {
        ...prev,
        players: data.players,
        readyStates: data.readyStates || prev.readyStates
      } : null);
    });

    s.on("deal_hand", data => {
      if (lobbyInfoRef.current && data.username === lobbyInfoRef.current.username) {
        setPlayerHand(data.hand);
      }
    });

    s.on("game_started", data => {
      setCurrentPlayer(data.current_player);
      setCurrentPlay(null);
      setLastPlayType(null);
      setSelectedCards([]);
      setCanEndRound(false);
      setPassedPlayers([]);
      setGameOverInfo(null);
    });

    s.on("game_update", data => {
      setCurrentPlay(data.current_play);
      setCurrentPlayer(data.current_player);
      setCanEndRound(data.can_end_round || false);
      setPassedPlayers(data.passed_players || []);
      setLastPlayType(data.last_play_type || null);
      if (lobbyInfoRef.current) {
        const username = lobbyInfoRef.current.username;
        if (data.hands && data.hands[username]) {
          setPlayerHand(data.hands[username]);
        }
      }
    });

    s.on("game_over", data => {
      setGameOverInfo(data);
      setCurrentPlayer(null);
      setCurrentPlay(null);
      setLastPlayType(null);
      setCanEndRound(false);
      setPassedPlayers([]);
    });

    s.on("error_msg", msg => { alert(msg); });

    return () => { s.disconnect(); };
    // eslint-disable-next-line
  }, []);

  const handleCreateRoom = ({ username, cardBack, wildCards }) => {
    if (socket) socket.emit("create_room", { username, cardBack, wildCards });
  };

  const handleJoinRoom = ({ username, roomId }) => {
    if (socket) socket.emit("join_room", { username, roomId });
  };

  const toggleReady = () => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username, readyStates } = lobbyInfo;
    const currentlyReady = readyStates ? readyStates[username] : false;
    socket.emit("set_ready", { roomId, username, ready: !currentlyReady });
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

  const endRound = () => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username } = lobbyInfo;
    socket.emit("end_round", { roomId, username });
  };

  if (inRoom && lobbyInfo) {
    const { roomId, username, players, settings, readyStates = {} } = lobbyInfo;
    const isCreator = players[0] === username;
    const allReady = players.every(player => readyStates[player]);
    const yourTurn = currentPlayer === username;

    // === GAME OVER VIEW ===
    if (gameOverInfo) {
      const { finish_order, hands } = gameOverInfo;
      return (
        <div style={{ textAlign: "center", marginTop: "3rem" }}>
          <h2>Game Over!</h2>
          <ol style={{ textAlign: "left", margin: "1rem auto", display: "inline-block" }}>
            {finish_order.map((player, i) => (
              <li key={player} style={{ fontWeight: player === username ? "bold" : undefined }}>
                {i === 0 ? "🥇 " : i === 1 ? "🥈 " : i === 2 ? "🥉 " : ""}
                {player} {player === username && "(You)"}
              </li>
            ))}
          </ol>
          <h3>Final Hands</h3>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {players.map(player => (
              <li key={player} style={{ marginBottom: 8 }}>
                <span style={{ fontWeight: player === username ? "bold" : undefined }}>
                  {player}:
                </span>
                {" "}
                {hands && hands[player] && hands[player].length > 0
                  ? hands[player].sort((a, b) => cardSortKey(a) - cardSortKey(b)).map(card => (
                      <img
                        key={card}
                        src={`${process.env.PUBLIC_URL}/cards/${card}.svg`}
                        alt={card}
                        style={{ width: 38, height: 54, margin: "0 1px", verticalAlign: "middle" }}
                      />
                    ))
                  : <span style={{ color: "#888" }}>Empty</span>
                }
              </li>
            ))}
          </ul>
          {isCreator && (
            <div style={{ marginTop: 24 }}>
              <button
                style={{
                  background: "#0083e1",
                  color: "#fff",
                  padding: "12px 32px",
                  fontSize: "1.2rem",
                  borderRadius: 8
                }}
                onClick={startGame}
              >
                Start New Game
              </button>
            </div>
          )}
        </div>
      );
    }

    // === NORMAL GAME VIEW ===
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
              {currentPlayer
                ? (
                  passedPlayers.includes(player)
                    ? <span style={{ color: "#ad0000" }}>⏸️ Passed</span>
                    : <span style={{ color: "#189a10" }}>▶️ Playing</span>
                )
                : (
                  <span style={{ color: readyStates[player] ? "green" : "gray" }}>
                    {readyStates[player] ? "✔️ Ready" : "⏳ Not Ready"}
                  </span>
                )
              }
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
              {currentPlay === null
                ? <span style={{ color: "#999" }}>None yet</span>
                : (
                  currentPlay.cards.length > 0
                    ? (
                        <>
                          {currentPlay.cards.map(card =>
                            <img
                              key={card}
                              src={`${process.env.PUBLIC_URL}/cards/${card}.svg`}
                              alt={card}
                              style={{ width: 40, height: 56, verticalAlign: "middle", marginRight: 3 }}
                            />
                          )}
                          {lastPlayType &&
                            <span style={{ marginLeft: 10, color: "#317cff", fontWeight: "bold" }}>
                              {handTypeLabelString(lastPlayType)}
                            </span>
                          }
                        </>
                      )
                    : <span>Pass</span>
                )
              }
              {currentPlay && currentPlay.player ? ` by ${currentPlay.player}` : ""}
            </div>
            <h3>Your hand:</h3>
            <div style={{ display: "flex", justifyContent: "center", flexWrap: "wrap", marginBottom: 10 }}>
              {[...playerHand]
                .sort((a, b) => cardSortKey(a) - cardSortKey(b))
                .map((card, idx) => {
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
                {canEndRound
                  ? (
                    <button
                      style={{ background: "#28a745", color: "#fff", padding: "10px 24px", fontSize: "1rem", borderRadius: 6 }}
                      onClick={endRound}
                    >
                      End Round
                    </button>
                  )
                  : (
                    <button onClick={passTurn}>Pass</button>
                  )
                }
              </>
            )}
            {!yourTurn && !canEndRound && <p>Waiting for <strong>{currentPlayer}</strong> to play...</p>}
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
