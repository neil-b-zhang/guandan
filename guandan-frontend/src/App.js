// guandan-frontend/src/App.js

import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import CreateJoinRoom from "./CreateJoinRoom";

// ---- Card mapping helpers ----
const CARD_RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2', 'JoB', 'JoR'];
const SUITS = ["hearts", "spades", "clubs", "diamonds"];
const SUIT_SYMBOLS = {
  hearts: "♥",
  spades: "♠",
  diamonds: "♦",
  clubs: "♣"
};
const SUIT_COLORS = {
  hearts: "#c62a41",
  diamonds: "#2288ff",
  spades: "#222",
  clubs: "#028b58"
};
const LEVEL_SEQUENCE = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];

// --- Helper: Card sorting key for showing hands ---
function cardSortKey(card, levelRank) {
  if (card === "JoR") return 100;
  if (card === "JoB") return 99;
  if (getCardRank(card) === levelRank) return 98;
  return CARD_RANK_ORDER.indexOf(getCardRank(card));
}
function getCardRank(card) {
  if (card === "JoB" || card === "JoR") return card;
  if (card.length === 3) return card.slice(0, 2);
  return card[0];
}
function getCardSuit(card) {
  if (card === "JoB" || card === "JoR") return null;
  const code = card.length === 3 ? card[2] : card[1];
  switch (code?.toUpperCase()) {
    case "H": return "hearts";
    case "S": return "spades";
    case "C": return "clubs";
    case "D": return "diamonds";
    default: return null;
  }
}
function isWild(card, levelRank, trumpSuit, wildCards) {
  if (!wildCards || !levelRank || !trumpSuit) return false;
  return getCardRank(card) === levelRank && getCardSuit(card) === trumpSuit;
}
function isTrump(card, levelRank, trumpSuit, wildCards) {
  if (card === "JoB" || card === "JoR") return true;
  if (!trumpSuit) return false;
  const suit = getCardSuit(card);
  const rank = getCardRank(card);
  if (suit === trumpSuit) return true;
  if (rank === levelRank) return true;
  return isWild(card, levelRank, trumpSuit, wildCards);
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
function teamName(teams, player) {
  if (!teams) return "";
  if (teams[0].includes(player)) return "Team A";
  if (teams[1].includes(player)) return "Team B";
  return "";
}
function seatTeam(idx) {
  return idx % 2 === 0 ? "A" : "B";
}

// ================= MAIN APP ===================
export default function App() {
  // Core game/lobby state
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
  const [levels, setLevels] = useState({});
  const [teams, setTeams] = useState([[], []]);
  const [slots, setSlots] = useState([null, null, null, null]);
  const [settings, setSettings] = useState({ cardBack: "red", wildCards: true, trumpSuit: "hearts", startingLevels: ["2", "2", "2", "2"] });
  const [levelRank, setLevelRank] = useState("2");
  const [wildCards, setWildCards] = useState(true); // default is now true!
  const [trumpSuit, setTrumpSuit] = useState("hearts");
  const [startingLevels, setStartingLevels] = useState(["2","2","2","2"]);
  const [hands, setHands] = useState({});
  const [errorMsg, setErrorMsg] = useState("");

  // Keep lobbyInfo ref updated
  useEffect(() => { lobbyInfoRef.current = lobbyInfo; }, [lobbyInfo]);

  // ---- SOCKET CONNECTION + EVENT HANDLERS ----
  useEffect(() => {
    const s = io("http://localhost:5000", { transports: ["polling"] });
    setSocket(s);

    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));

    // ---- Lobby/Game Join
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
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings(data.settings || { cardBack: "red", wildCards: true, trumpSuit: "hearts", startingLevels: ["2","2","2","2"] });
      setWildCards((data.settings && typeof data.settings.wildCards === "boolean") ? data.settings.wildCards : true);
      setTrumpSuit((data.settings && data.settings.trumpSuit) || "hearts");
      setStartingLevels((data.settings && data.settings.startingLevels) || ["2","2","2","2"]);
      setLevelRank((data.levelRank) || "2");
      setHands({});
    });

    // ---- Room Update: keeps lobby state in sync for everyone
    s.on("room_update", data => {
      setLobbyInfo(prev => prev ? {
        ...prev,
        players: data.players,
        readyStates: data.readyStates ?? {},
        slots: data.slots ?? prev.slots,
      } : null);
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings(data.settings || { cardBack: "red", wildCards: true, trumpSuit: "hearts", startingLevels: ["2","2","2","2"] });
      setWildCards((data.settings && typeof data.settings.wildCards === "boolean") ? data.settings.wildCards : true);
      setTrumpSuit((data.settings && data.settings.trumpSuit) || "hearts");
      setStartingLevels((data.settings && data.settings.startingLevels) || ["2","2","2","2"]);
    });

    // ---- Deal your hand privately
    s.on("deal_hand", data => {
      if (lobbyInfoRef.current && data.username === lobbyInfoRef.current.username) {
        setPlayerHand(data.hand);
      }
    });

    // ---- Game Start
    s.on("game_started", data => {
      setCurrentPlayer(data.current_player);
      setCurrentPlay(null);
      setLastPlayType(null);
      setSelectedCards([]);
      setCanEndRound(false);
      setPassedPlayers([]);
      setGameOverInfo(null);
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings(data.settings || { cardBack: "red", wildCards: true, trumpSuit: "hearts", startingLevels: ["2","2","2","2"] });
      setWildCards((typeof data.wildCards === "boolean") ? data.wildCards : true);
      setTrumpSuit((data.trumpSuit) || "hearts");
      setStartingLevels((data.startingLevels) || ["2","2","2","2"]);
      setLevelRank((data.levelRank) || "2");
      setHands(data.hands || {});
    });

    // ---- In-game updates (after every move)
    s.on("game_update", data => {
      setCurrentPlay(data.current_play);
      setCurrentPlayer(data.current_player);
      setCanEndRound(data.can_end_round || false);
      setPassedPlayers(data.passed_players || []);
      setLastPlayType(data.last_play_type || null);
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings(data.settings || { cardBack: "red", wildCards: true, trumpSuit: "hearts", startingLevels: ["2","2","2","2"] });
      setWildCards((typeof data.wildCards === "boolean") ? data.wildCards : true);
      setTrumpSuit((data.trumpSuit) || "hearts");
      setStartingLevels((data.startingLevels) || ["2","2","2","2"]);
      setLevelRank((data.levelRank) || "2");
      setHands(data.hands || {});
      if (lobbyInfoRef.current) {
        const username = lobbyInfoRef.current.username;
        if (data.hands && data.hands[username]) {
          setPlayerHand(data.hands[username]);
        }
      }
    });

    // ---- Game End
    s.on("game_over", data => {
      setGameOverInfo(data);
      setCurrentPlayer(null);
      setCurrentPlay(null);
      setLastPlayType(null);
      setCanEndRound(false);
      setPassedPlayers([]);
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings(data.settings || { cardBack: "red", wildCards: true, trumpSuit: "hearts", startingLevels: ["2","2","2","2"] });
      setWildCards((typeof data.wildCards === "boolean") ? data.wildCards : true);
      setTrumpSuit((data.trumpSuit) || "hearts");
      setStartingLevels((data.startingLevels) || ["2","2","2","2"]);
      setLevelRank((data.levelRank) || "2");
      setHands(data.hands || {});
    });

    // ---- Error messages
    s.on("error_msg", msg => { setErrorMsg(msg); alert(msg); });

    return () => { s.disconnect(); };
    // eslint-disable-next-line
  }, []);

  // ---- ROOM ACTION HANDLERS ----
  const handleCreateRoom = ({ username, roomName }) => {
    if (socket) socket.emit("create_room", {
      username,
      roomName,
      cardBack: "red",
      wildCards: true, // default to "Leading Team's Level"
      trumpSuit: "hearts",
      startingLevels: ["2", "2", "2", "2"]
    });
  };
  const handleJoinRoom = ({ username, roomId }) => {
    if (socket) socket.emit("join_room", { username, roomId });
  };

  // ---- GAMEPLAY ACTIONS ----
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

  // ---- LOBBY SETTINGS ----
  const handleChangeTrump = (suit) => {
    if (!socket || !lobbyInfo) return;
    setTrumpSuit(suit);
    const newSettings = { ...settings, trumpSuit: suit };
    setSettings(newSettings);
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings
    });
  };
  const handleChangeWild = (enabled) => {
    if (!socket || !lobbyInfo) return;
    setWildCards(enabled);
    const newSettings = { ...settings, wildCards: enabled };
    setSettings(newSettings);
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings
    });
  };
  const handleChangeStartingLevel = (slotIdx, newLevel) => {
    if (!socket || !lobbyInfo) return;
    const updated = [...startingLevels];
    updated[slotIdx] = newLevel;
    setStartingLevels(updated);
    const newSettings = { ...settings, startingLevels: updated };
    setSettings(newSettings);
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings
    });
  };
  const handleMoveSeat = (idx) => {
    if (!socket || !lobbyInfo) return;
    const { roomId, username } = lobbyInfo;
    socket.emit("move_seat", { roomId, username, slotIdx: idx });
  };

  // --- RENDER ERROR BANNER ---
  function renderErrorBanner() {
    return errorMsg ? (
      <div style={{
        background: "#ffeaea",
        color: "#a30000",
        border: "1.5px solid #ffaaaa",
        borderRadius: 7,
        margin: "0.7rem auto 0.6rem auto",
        maxWidth: 430,
        padding: "0.7rem 1.1rem",
        fontWeight: "bold"
      }}>
        {errorMsg}
      </div>
    ) : null;
  }

  // === GAME OVER VIEW ===
  if (inRoom && lobbyInfo && gameOverInfo) {
    const { roomId, username } = lobbyInfo;
    const { finish_order, hands: finalHands, levels: finalLevels, teams: finalTeams, winning_team, win_type, level_up, trumpSuit: gameTrump, levelRank: gameLevel, wildCards: gameWilds } = gameOverInfo;
    return (
      <div style={{ textAlign: "center", marginTop: "2rem" }}>
      {renderErrorBanner()}
        <h2>Game Over!</h2>
        <div style={{ margin: "1rem 0" }}>
          <strong>Trump Suit:</strong>{" "}
          <span style={{ color: SUIT_COLORS[gameTrump] || "#444", fontWeight: "bold" }}>
            {SUIT_SYMBOLS[gameTrump] || ""}
            {gameTrump && gameTrump.charAt(0).toUpperCase() + gameTrump.slice(1)}
          </span>{" "}
          | <strong>Level:</strong> <span style={{ color: "#ea6700" }}>{gameLevel}</span>
          {" | "}
          <strong>Wild:</strong> <span style={{ color: "#9e3ad7" }}>{gameWilds ? "Leading Team's Level" : "None"}</span>
        </div>
        <div style={{ fontSize: 20, margin: "1rem 0" }}>
          <strong>Result:</strong>{" "}
          {win_type
            ? (
              <>
                <span style={{ color: "#006410", fontWeight: 600 }}>
                  {win_type} Win
                </span>{" "}
                | Winning Team:{" "}
                <span style={{ color: "#0069d9" }}>
                  {winning_team ? winning_team.join(", ") : ""}
                </span>{" "}
                | Level Up: <span style={{ color: "#ea6700", fontWeight: 600 }}>+{level_up}</span>
              </>
            )
            : null
          }
        </div>
        <div>
          <strong>Teams:</strong>{" "}
          <span style={{ color: "#1976d2" }}>
            A: {finalTeams && finalTeams[0].join(", ")} &nbsp;&nbsp; B: {finalTeams && finalTeams[1].join(", ")}
          </span>
        </div>
        <ol style={{ textAlign: "left", margin: "1rem auto", display: "inline-block" }}>
          {finish_order.map((player, i) => (
            <li key={player} style={{ fontWeight: player === lobbyInfo.username ? "bold" : undefined }}>
              {i === 0 ? "🥇 " : i === 1 ? "🥈 " : i === 2 ? "🥉 " : ""}
              {player} {player === lobbyInfo.username && "(You)"}
              {" "}
              <span style={{
                color: (winning_team && winning_team.includes(player)) ? "#1976d2" : "#a06d2d",
                fontWeight: 500,
                marginLeft: 4
              }}>
                [{teamName(finalTeams, player)}]
              </span>
              {" "}
              <span style={{
                color: "#ea6700",
                fontWeight: 600
              }}>
                Level {finalLevels && finalLevels[player]}
              </span>
            </li>
          ))}
        </ol>
        <h3>Final Hands</h3>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {slots.map((player, idx) =>
            <li key={idx} style={{ marginBottom: 8 }}>
              <span style={{ fontWeight: player === lobbyInfo.username ? "bold" : undefined }}>
                {player || <span style={{ color: "#888" }}>Empty</span>}:
              </span>
              {" "}
              {player && finalHands && finalHands[player] && finalHands[player].length > 0
                ? finalHands[player].sort((a, b) => cardSortKey(a, gameLevel) - cardSortKey(b, gameLevel)).map(card => (
                    <CardImg
                      key={card}
                      card={card}
                      trumpSuit={gameTrump}
                      levelRank={gameLevel}
                      wildCards={gameWilds}
                      highlightWild
                      highlightTrump
                      style={{ width: 38, height: 54, margin: "0 1px", verticalAlign: "middle" }}
                    />
                  ))
                : <span style={{ color: "#888" }}>Empty</span>
              }
            </li>
          )}
        </ul>
        {slots[0] === lobbyInfo.username && (
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

  // === LOBBY SCREEN (BEFORE GAME) ===
  if (inRoom && lobbyInfo && !currentPlayer) {
    const { roomId, username, readyStates = {} } = lobbyInfo;
    const isCreator = slots[0] === username;
    const allReady = slots.filter(Boolean).every(player => readyStates[player]);
    return (
      <div style={{ textAlign: "center", marginTop: "2.2rem" }}>
        {renderErrorBanner()}
        <h1>Room {roomId}</h1>
        <h3 style={{ color: "#5c6bc0" }}>Lobby</h3>
        <div style={{ marginBottom: "1.2rem" }}>
          <strong>Trump Suit: </strong>
          {isCreator ? (
            <select value={trumpSuit} onChange={e => handleChangeTrump(e.target.value)} style={{ fontSize: 18 }}>
              {SUITS.map(suit =>
                <option key={suit} value={suit}>{SUIT_SYMBOLS[suit]} {suit.charAt(0).toUpperCase() + suit.slice(1)}</option>
              )}
            </select>
          ) : (
            <span style={{ color: SUIT_COLORS[trumpSuit], fontWeight: "bold" }}>
              {SUIT_SYMBOLS[trumpSuit]} {trumpSuit.charAt(0).toUpperCase() + trumpSuit.slice(1)}
            </span>
          )}
          <span style={{ marginLeft: 30 }}>
            <strong>Wild Cards: </strong>
            {isCreator ? (
              <select value={wildCards ? "level" : "none"} onChange={e => handleChangeWild(e.target.value === "level")} style={{ fontSize: 18 }}>
                <option value="none">No Wild Cards</option>
                <option value="level">Leading Team's Level</option>
              </select>
            ) : (
              <span style={{ color: "#9e3ad7", fontWeight: "bold" }}>
                {wildCards ? "Leading Team's Level" : "None"}
              </span>
            )}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "center", gap: "6rem", margin: "1.6rem 0" }}>
          <TeamColumn team="A" slotIndices={[0,2]} slots={slots} yourName={username}
            isCreator={isCreator} startingLevels={startingLevels}
            onMove={handleMoveSeat} onChangeStartingLevel={handleChangeStartingLevel}
          />
          <TeamColumn team="B" slotIndices={[1,3]} slots={slots} yourName={username}
            isCreator={isCreator} startingLevels={startingLevels}
            onMove={handleMoveSeat} onChangeStartingLevel={handleChangeStartingLevel}
          />
        </div>
        <div>
          <strong>Your Level: </strong>
          <span style={{ color: "#ea6700" }}>{levels[username]}</span>
          {" | "}
          <strong>Your Team: </strong>
          <span style={{ color: "#317cff" }}>{seatTeam(slots.indexOf(username)) === "A" ? "Team A" : "Team B"}</span>
        </div>
        <div style={{ margin: "2rem 0" }}>
          <button onClick={toggleReady} style={{ marginRight: 10 }}>
            {readyStates[username] ? "Unready" : "Ready"}
          </button>
          {isCreator && (
            <button disabled={!allReady || slots.filter(Boolean).length < 2} onClick={startGame}>
              Start Game
            </button>
          )}
        </div>
      </div>
    );
  }

  // ---- 3. GAMEPLAY SCREEN (show hands: yours face up, others as card backs) ----
  if (inRoom && lobbyInfo && currentPlayer) {
    const { roomId, username, readyStates = {} } = lobbyInfo;
    const yourTurn = currentPlayer === username;

    // Compute each team's level for the current round (minimum of player levels)
    const teamALevel = teams[0] && teams[0].length
      ? LEVEL_SEQUENCE[Math.min(...teams[0].map(p => LEVEL_SEQUENCE.indexOf(levels[p] || "2")))]
      : "-";
    const teamBLevel = teams[1] && teams[1].length
      ? LEVEL_SEQUENCE[Math.min(...teams[1].map(p => LEVEL_SEQUENCE.indexOf(levels[p] || "2")))]
      : "-";

    console.log("hands object:", hands);

    return (
      <div style={{ textAlign: "center", marginTop: "2.2rem" }}>
        {/* Game Info Bar */}
        <div style={{ marginBottom: 8, fontWeight: 600 }}>
          Trump Suit: <span style={{ color: SUIT_COLORS[trumpSuit], fontWeight: "bold" }}>
            {SUIT_SYMBOLS[trumpSuit]} {trumpSuit.charAt(0).toUpperCase() + trumpSuit.slice(1)}
          </span>
          {" | "}
          Current Level: <span style={{ color: "#ea6700" }}>{levelRank}</span>
          {" | "}
          Wild: <span style={{ color: "#9e3ad7", fontWeight: "bold" }}>
            {wildCards ? "Leading Team's Level" : "None"}
          </span>
        </div>
        {/* Team Status */}
        <div style={{ marginBottom: 10 }}>
          <strong>Team A Level:</strong>{" "}
          <span style={{ color: "#ea6700" }}>{teamALevel}</span>
          {" | "}
          <strong>Team B Level:</strong>{" "}
          <span style={{ color: "#ea6700" }}>{teamBLevel}</span>
        </div>
        {/* All Hands: Show only opponents (face down), NOT your own hand here! */}
        <div style={{
          display: "flex",
          justifyContent: "center",
          gap: "2.5rem",
          marginBottom: "2rem"
        }}>
          {slots.map((player, idx) => {
            if (!player) {
              return (
                <div key={idx} style={{ minWidth: 110, opacity: 0.5 }}>
                  <div style={{ height: 60 }}></div>
                  <div style={{ fontSize: 16, color: "#bbb" }}>Empty</div>
                </div>
              );
            }
            if (player === lobbyInfo.username) {
              return <div key={player} style={{ minWidth: 110 }}></div>;
            }
            const hand = hands && hands[player] ? hands[player] : [];
            return (
              <div key={player} style={{ minWidth: 110 }}>
                <div style={{ marginBottom: 4 }}>{player}</div>
                <div style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  height: 60
                }}>
                  {Array.from({ length: hand.length }).map((_, i) => (
                    <img
                      key={i}
                      src={process.env.PUBLIC_URL + `/cards/back_${settings.cardBack[0]}.svg`}
                      alt="Back"
                      style={{
                        width: 36,
                        height: 52,
                        marginLeft: i === 0 ? 0 : -14,
                        borderRadius: 6,
                        border: "1px solid #aaa",
                        background: "#eee"
                      }}
                    />
                  ))}
                </div>
                <div style={{ fontSize: 12, color: "#555" }}>
                  Cards: {hand.length}
                </div>
              </div>
            );
          })}
        </div>

        {/* Player status list */}
        <ul style={{ listStyle: "none", padding: 0, margin: "1.4rem 0 1.2rem 0" }}>
          {slots.map((player, idx) => (
            <li key={idx}>
              <span style={{
                fontWeight: player === lobbyInfo.username ? "bold" : undefined,
                fontSize: 18
              }}>
                {player || <span style={{ color: "#bbb" }}>Empty</span>}
              </span>
              {" "}
              <span style={{
                color: idx % 2 === 0 ? "#1976d2" : "#a06d2d",
                fontWeight: 500,
                marginLeft: 4
              }}>
                [{seatTeam(idx) === "A" ? "Team A" : "Team B"}]
              </span>
              {" "}
              {player &&
                <span style={{
                  color: "#ea6700",
                  fontWeight: 600,
                  marginLeft: 2
                }}>
                  Lvl {levels[player]}
                </span>
              }
              {" "}
              {player && currentPlayer
                ? (
                  passedPlayers.includes(player)
                    ? <span style={{ color: "#ad0000" }}>⏸️ Passed</span>
                    : <span style={{ color: "#189a10" }}>▶️ Playing</span>
                )
                : player && (
                  <span style={{ color: readyStates[player] ? "green" : "gray" }}>
                    {readyStates[player] ? "✔️ Ready" : "⏳ Not Ready"}
                  </span>
                )
              }
            </li>
          ))}
        </ul>
        <h3>Current turn: <span style={{ color: yourTurn ? "#0048ab" : undefined }}>{currentPlayer}</span></h3>
        {/* Last play area */}
        <div style={{ marginBottom: 10 }}>
          <strong>Last play:</strong>{" "}
          {currentPlay === null
            ? <span style={{ color: "#999" }}>None yet</span>
            : (
              currentPlay.cards.length > 0
                ? (
                    <>
                      {currentPlay.cards.map(card =>
                        <CardImg
                          key={card}
                          card={card}
                          trumpSuit={trumpSuit}
                          levelRank={levelRank}
                          wildCards={wildCards}
                          highlightWild
                          highlightTrump
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
        {/* === Your hand: full sized, overlapped, selectable === */}
        <h3>Your hand:</h3>
        <div style={{ display: "flex", justifyContent: "center", flexWrap: "wrap", marginBottom: 10 }}>
          {[...playerHand]
            .sort((a, b) => cardSortKey(a, levelRank) - cardSortKey(b, levelRank))
            .map((card, idx) => {
              const isSelected = selectedCards.includes(card);
              return (
                <CardImg
                  key={card + idx}
                  card={card}
                  trumpSuit={trumpSuit}
                  levelRank={levelRank}
                  wildCards={wildCards}
                  highlightWild
                  highlightTrump
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
                    marginLeft: idx === 0 ? 0 : -24, // Overlap for your hand
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
        {/* Play/pass/end round controls */}
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
      </div>
    );
  }

  // ---- 4. LANDING/Lobby screen ----
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

// ==== Helper Components ====

function TeamColumn({ team, slotIndices, slots, yourName, isCreator, startingLevels, onMove, onChangeStartingLevel }) {
  return (
    <div>
      <h4 style={{ color: team === "A" ? "#1976d2" : "#a06d2d" }}>Team {team}</h4>
      {slotIndices.map(idx => (
        <LobbySeat
          key={idx}
          idx={idx}
          player={slots[idx]}
          yourName={yourName}
          isCreator={isCreator}
          startingLevel={startingLevels[idx]}
          onMove={onMove}
          onChangeStartingLevel={onChangeStartingLevel}
        />
      ))}
    </div>
  );
}

function LobbySeat({ idx, player, yourName, isCreator, startingLevel, onMove, onChangeStartingLevel }) {
  return (
    <div style={{
      margin: "1.2rem 0",
      minWidth: 140,
      display: "flex",
      flexDirection: "column",
      alignItems: "center"
    }}>
      <div style={{
        border: "2px dashed #bbb",
        borderRadius: 10,
        background: player ? "#f7f7fa" : "#f9f9f2",
        minHeight: 32,
        fontSize: 20,
        color: player ? "#333" : "#bbb",
        fontWeight: player ? "bold" : undefined,
        padding: "8px 0",
        width: "100px"
      }}>
        {player || "Empty"}
      </div>
      <div style={{ marginTop: 4, marginBottom: 3 }}>
        <span style={{
          color: "#ea6700",
          fontWeight: 600
        }}>
          Level:{" "}
          {isCreator
            ? (
              <select
                value={startingLevel}
                onChange={e => onChangeStartingLevel(idx, e.target.value)}
                style={{ fontSize: 16 }}
              >
                {LEVEL_SEQUENCE.map(lv =>
                  <option key={lv} value={lv}>{lv}</option>
                )}
              </select>
            )
            : <span>{startingLevel}</span>
          }
        </span>
      </div>
      {/* Slot alignment fix: always show 22px-high div for (You), even if not user */}
      <div style={{ height: 22, marginTop: 4 }}>
        {player === yourName
          ? <span style={{ color: "#317cff" }}>(You)</span>
          : <span style={{ visibility: "hidden" }}>(You)</span>
        }
      </div>
      {!player && yourName &&
        <button style={{ marginTop: 4 }} onClick={() => onMove(idx)}>
          Sit Here
        </button>
      }
    </div>
  );
}

// --- CardImg: Renders a single card face or (optionally) highlights trump/wild ---
function CardImg({ card, trumpSuit, levelRank, wildCards, onClick, highlightWild, highlightTrump, style }) {
  const isJoker = card === "JoB" || card === "JoR";
  const suit = getCardSuit(card);
  const rank = getCardRank(card);
  const wild = isWild(card, levelRank, trumpSuit, wildCards);
  const trump = isTrump(card, levelRank, trumpSuit, wildCards);
  return (
    <img
      src={process.env.PUBLIC_URL + `/cards/${card}.svg`}
      alt={card}
      onClick={onClick}
      style={{
        border: highlightWild && wild ? "3px solid #9e3ad7" :
                highlightTrump && trump ? "2.5px solid #c62a41" : "1px solid #aaa",
        borderRadius: 6,
        boxShadow: wild ? "0 0 9px #9e3ad7" :
                  trump ? "0 0 7px #c62a41" : undefined,
        background: isJoker ? "#f6f5ee" : "#fff",
        ...style
      }}
      title={
        wild ? "Wild Card" :
        trump ? "Trump Card" : ""
      }
    />
  );
}
