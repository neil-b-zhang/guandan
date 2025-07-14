// guandan-frontend/src/App.js

import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import CreateJoinRoom from "./CreateJoinRoom";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors
} from '@dnd-kit/core';
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
  arrayMove
} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';

// ---- default settings ----
const DEFAULT_SETTINGS = {
  cardBack: "red",
  wildCards: true,
  trumpSuit: "hearts",
  startingLevels: ["2", "2", "2", "2"],
  showCardCount: false,
  highlightWilds: false
};


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
  if (!card || typeof card !== "string") return "";
  if (card === "JoB" || card === "JoR") return card;
  if (card.length === 3) return card.slice(0, 2);
  return card[0];
}
function getCardSuit(card) {
  if (!card || typeof card !== "string") return null;
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

function SortableCard({ card, idx, ...props }) {
  const {attributes, listeners, setNodeRef, transform, transition, isDragging} = useSortable({id: card + idx});
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 10 : 1,
        display: "inline-block",
        marginLeft: idx === 0 ? 0 : -24,
      }}
    >
      <CardImg card={card} {...props} />
    </div>
  );
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
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [levelRank, setLevelRank] = useState("2");
  const [wildCards, setWildCards] = useState(true); // default is now true!
  const [trumpSuit, setTrumpSuit] = useState("hearts");
  const [startingLevels, setStartingLevels] = useState(["2","2","2","2"]);
  const [hands, setHands] = useState({});
  const [errorMsg, setErrorMsg] = useState("");
  const [handOrder, setHandOrder] = useState([]);
  const [tributeState, setTributeState] = useState(null);
  const [finishOrder, setFinishOrder] = useState([]);
  const [gamePhase, setGamePhase] = useState("lobby"); // "lobby" | "game" | "hand_over"
  const [handOverInfo, setHandOverInfo] = useState(null);

  // Store last hand length to detect when new cards are dealt
  const prevHandLength = useRef(0);
  useEffect(() => {
    // Only reset handOrder when a NEW hand is dealt (length increases)
    if (playerHand.length > 0 && playerHand.length !== prevHandLength.current) {
      // Sort the new hand by rank for first deal, or whatever order you want
      setHandOrder([...playerHand].sort((a, b) => cardSortKey(a, levelRank) - cardSortKey(b, levelRank)));
      prevHandLength.current = playerHand.length;
    }
    // If playerHand is emptied, reset prevHandLength
    if (playerHand.length === 0) prevHandLength.current = 0;
    // eslint-disable-next-line
  }, [playerHand, levelRank]);

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
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
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
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
      setWildCards((data.settings && typeof data.settings.wildCards === "boolean") ? data.settings.wildCards : true);
      setTrumpSuit((data.settings && data.settings.trumpSuit) || "hearts");
      setStartingLevels((data.settings && data.settings.startingLevels) || ["2","2","2","2"]);
    });

    // ---- Deal your hand privately
    s.on("deal_hand", data => {
      if (lobbyInfoRef.current && data.username === lobbyInfoRef.current.username) {
        // Sort the new hand in value order (using the current level)
        const sortedHand = [...data.hand].sort(
          (a, b) => cardSortKey(a, levelRank) - cardSortKey(b, levelRank)
        );
        setPlayerHand(sortedHand);
        setHandOrder(sortedHand); // Also reset the handOrder for drag-and-drop
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
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
      setWildCards((typeof data.wildCards === "boolean") ? data.wildCards : true);
      setTrumpSuit((data.trumpSuit) || "hearts");
      setStartingLevels((data.startingLevels) || ["2","2","2","2"]);
      setLevelRank((data.levelRank) || "2");
      setHands(data.hands || {});
      setGamePhase("game");
    });

    // ---- In-game updates (after every move)
    s.on("game_update", data => {
      console.log("[SOCKET] Game update:");
      console.log("  current_player:", data.current_player);
      console.log("  can_end_round:", data.can_end_round);
      console.log("  finish_order:", data.finish_order);
      console.log("  passed_players:", data.passed_players);
      setCurrentPlay(data.current_play);
      setCurrentPlayer(data.current_player);
      setCanEndRound(data.can_end_round || false);
      setPassedPlayers(data.passed_players || []);
      setLastPlayType(data.last_play_type || null);
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
      setWildCards((typeof data.wildCards === "boolean") ? data.wildCards : true);
      setTrumpSuit((data.trumpSuit) || "hearts");
      setStartingLevels((data.startingLevels) || ["2","2","2","2"]);
      setLevelRank((data.levelRank) || "2");
      setHands(data.hands || {});
      if (Array.isArray(data.finish_order) && data.finish_order.length > 0) {
        setFinishOrder(data.finish_order);
      }


      if (lobbyInfoRef.current) {
        const username = lobbyInfoRef.current.username;
        if (data.hands && data.hands[username]) {
          setPlayerHand(data.hands[username]);
        }
      }
    });

    s.on("hand_over", (data) => {
      console.log("[HAND OVER]", data);
      setHandOverInfo(data.result);  // contains { levels, win_type, winning_team, ... }
      setGamePhase("hand_over");     // You can render a summary screen in this state
    });

    // ---- Round End
    // === Round end handlers ===
   s.on("round_summary", ({ roomId, finishOrder, result }) => {
      console.log("[ROUND SUMMARY]", finishOrder, result);

      setLevels(result.levels || {});
      setFinishOrder(finishOrder || []);
      setTeams(result.teams || [[], []]);
      setSlots(result.slots || [null, null, null, null]);

      // ✅ Update dropdown values to reflect actual levels
      if (result.levels && slots.length === 4) {
        const newStartingLevels = slots.map(player => result.levels[player] || "2");
        setStartingLevels(newStartingLevels);
      }

      setGamePhase("lobby");
    });



    // === Tribute handlers ===
    s.on("tribute_start", (data) => setTributeState(data));
    s.on("tribute_update", (data) => setTributeState(data.tribute_state));
    s.on("tribute_prompt_return", (data) => setTributeState(data.tribute_state));
    s.on("tribute_complete", (data) => {
      setTributeState(null);
      setHands(data.hands || {});
    });

    // ---- Game End
    s.on("game_over", data => {
      console.log("[game_over]", data);
      setGameOverInfo(data);
      setCurrentPlayer(null);
      setCurrentPlay(null);
      setLastPlayType(null);
      setCanEndRound(false);
      setPassedPlayers([]);
      setLevels(data.levels || {});
      setTeams(data.teams || [[], []]);
      setSlots(data.slots || [null, null, null, null]);
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
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
    // Send the actual selected card values in order, using idx for accuracy
    socket.emit("play_cards", {
      roomId,
      username,
      cards: selectedCards.map(sel => handOrder[sel.idx]) // or sel.card if your backend expects only card names
    });
    setHandOrder(
      handOrder.filter((_, idx) =>
        !selectedCards.some(sel => sel.idx === idx)
      )
    );
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
    setSettings({ ...DEFAULT_SETTINGS, ...newSettings });
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings
    });
  };
  const handleChangeWild = (enabled) => {
    if (!socket || !lobbyInfo) return;
    setWildCards(enabled);
    const newSettings = { ...settings, wildCards: enabled };
    setSettings({ ...DEFAULT_SETTINGS, ...newSettings });
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
    setSettings({ ...DEFAULT_SETTINGS, ...newSettings });
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

  const handleChangeCardBack = (color) => {
    if (!socket || !lobbyInfo) return;
    const newSettings = { ...settings, cardBack: color };
    setSettings({ ...DEFAULT_SETTINGS, ...newSettings });
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings
    });
  };

  const handleChangeShowCardCount = (enabled) => {
    if (!socket || !lobbyInfo) return;
    const newSettings = { ...settings, showCardCount: enabled };
    setSettings({ ...DEFAULT_SETTINGS, ...newSettings });
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings
    });
  };

  const handleChangeHighlightWilds = (enabled) => {
    if (!socket || !lobbyInfo) return;
    const newSettings = { ...settings, highlightWilds: enabled };
    setSettings({ ...DEFAULT_SETTINGS, ...newSettings });
    socket.emit("update_room_settings", {
      roomId: lobbyInfo.roomId,
      settings: newSettings,
    });
  };

  // ---- PLAYER HAND CARD DRAGGING ----
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

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
      {/* Tribute overlay appears for all players when tributeState is set */}
      {tributeState && (
        <TributeOverlay
          tributeState={tributeState}
          setTributeState={setTributeState}
          socket={socket}
          playerName={lobbyInfo?.username}
          hands={hands}
        />
      )}
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

    console.log("settings.highlightWilds in App:", settings.highlightWilds);

    return (

      /* Card Back & Show Card Counter */
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

        {/* Card Back, Show Card Counter, Highlight Wilds -- ALL TOGETHER! */}
        <div
          style={{
            marginTop: 14,
            marginBottom: 10,
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 26,
            justifyContent: "center"
          }}
        >
          {/* Card Back */}
          <span>
            <strong>Card Back:</strong>{" "}
            {isCreator ? (
              <select
                value={settings.cardBack}
                onChange={e => handleChangeCardBack(e.target.value)}
                style={{ fontSize: 18, marginLeft: 4 }}
              >
                <option value="red">Red</option>
                <option value="black">Black</option>
              </select>
            ) : (
              <span style={{ color: "#ba1e1e", fontWeight: "bold" }}>
                {settings.cardBack.charAt(0).toUpperCase() + settings.cardBack.slice(1)}
              </span>
            )}
          </span>
          {/* Show Card Count */}
          <span>
            <strong>Show Opponent Card Counter:</strong>{" "}
            {isCreator ? (
              <input
                type="checkbox"
                checked={!!settings.showCardCount}
                onChange={e => handleChangeShowCardCount(e.target.checked)}
                style={{ transform: "scale(1.4)", marginLeft: 7, marginRight: 2 }}
              />
            ) : (
              <span style={{ color: "#1c2c8d", fontWeight: "bold", marginLeft: 5 }}>
                {settings.showCardCount ? "On" : "Off"}
              </span>
            )}
          </span>
          {/* Highlight Wilds */}
          <span>
            <strong>Highlight Wild Cards in Hand:</strong>{" "}
            {isCreator ? (
              <input
                type="checkbox"
                checked={!!settings.highlightWilds}
                onChange={e => handleChangeHighlightWilds(e.target.checked)}
                style={{ transform: "scale(1.4)", marginLeft: 7, marginRight: 2 }}
              />
            ) : (
              <span style={{ color: "#7d39b3", fontWeight: "bold", marginLeft: 5 }}>
                {settings.highlightWilds ? "On" : "Off"}
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

    // === If tributeState is active, show the overlay and block all game UI ===
    if (tributeState) {
      return (
        <>
          <TributeOverlay
            tributeState={tributeState}
            setTributeState={setTributeState}
            socket={socket}
            playerName={lobbyInfo?.username}
            hands={hands}
          />
        </>
      );
    }

    return (
      <div style={{ 
          maxWidth: 900,
          margin: "0 auto",
          padding: "0 24px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "100%",
        }}>

        {/* Game Info Bar */}
        <div style={{ paddingTop: 22, marginBottom: 8, fontWeight: 600 }}>
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
        
        {/* Player status list as a real table */}
        <table
          style={{
            width: "100%",
            maxWidth: 600,
            margin: "0 auto 1.2rem auto",
            borderCollapse: "collapse",
            fontSize: 15,
            background: "#fff"
          }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #ddd" }}>
              <th style={{ textAlign: "left", padding: "5px 10px", fontWeight: 700 }}>Player</th>
              <th style={{ textAlign: "left", padding: "5px 10px", fontWeight: 700 }}>Team</th>
              <th style={{ textAlign: "left", padding: "5px 10px", fontWeight: 700 }}>Level</th>
              <th style={{ textAlign: "left", padding: "5px 10px", fontWeight: 700 }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((player, idx) => {
              const teamLabel = seatTeam(idx) === "A"
                ? <span style={{ color: "#1976d2" }}>A</span>
                : <span style={{ color: "#a06d2d" }}>B</span>;
              const isCurrent = player === lobbyInfo.username;
              let statusCell = "";
              if (player) {
                if (finishOrder && finishOrder.includes(player)) {
                  const placement = finishOrder.indexOf(player);
                  const placeText = ["🥇 1st", "🥈 2nd", "🥉 3rd", "4th"][placement];
                  statusCell = <span style={{ color: "#4b0082", fontWeight: "bold" }}>{placeText}</span>;
                } else if (currentPlayer) {
                  if (passedPlayers.includes(player)) {
                    statusCell = <span style={{ color: "#ad0000" }}>⏸️ Passed</span>;
                  } else if (player === currentPlayer) {
                    statusCell = <span style={{ color: "#189a10" }}>▶️ Playing</span>;
                  } else {
                    statusCell = <span style={{ color: "#888" }}>Waiting</span>;
                  }
                } else {
                  statusCell = (
                    <span style={{ color: readyStates[player] ? "green" : "gray" }}>
                      {readyStates[player] ? "✔️ Ready" : "⏳ Not Ready"}
                    </span>
                  );
                }
              }
              return (
                <tr key={idx} style={{
                  background: idx % 2 === 1 ? "#f8fafd" : "#fff",
                  color: player ? "#222" : "#bbb",
                  fontWeight: isCurrent ? "bold" : 400,
                  height: 28
                }}>
                  <td style={{ padding: "2px 10px", minWidth: 50 }}>
                    {player || <span style={{ color: "#bbb" }}>Empty</span>}
                  </td>
                  <td style={{ padding: "2px 10px" }}>
                    {teamLabel}
                  </td>
                  <td style={{ padding: "2px 10px" }}>
                    {player && levels[player]
                      ? <span style={{ color: "#ea6700" }}>Lvl {levels[player]}</span>
                      : ""}
                  </td>
                  <td style={{ padding: "2px 10px", minWidth: 70 }}>{statusCell}</td>
                </tr>
              );
            })}
          </tbody>
        </table>


        {/* Opponents' Hands Display */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            width: "100%",
            margin: "0 auto 24px auto",
            padding: "0 8px",
            boxSizing: "border-box",
            gap: "12px",
          }}
        >
          {slots.map((player, idx) => {
            if (!player || player === lobbyInfo.username) return null;

            const hand = hands && hands[player] ? hands[player] : [];
            const maxCardWidth = 36;
            const cardCount = hand.length;

            // Container is always 100%, but inner stack is absolute-positioned
            const boxWidth = 120; // px - can adjust this to fit your design, try 100-160px
            const minOverlap = 7; // minimal visible part
            // overlap so all cards fit in boxWidth
            const overlap = cardCount > 1
              ? Math.max(
                  maxCardWidth - ((boxWidth - maxCardWidth) / (cardCount - 1)),
                  minOverlap
                )
              : 0;

            return (
              <div
                key={player}
                style={{
                  flex: "1 1 0",
                  minWidth: 90,
                  maxWidth: 220,
                  padding: "14px 6px 10px 6px",
                  border: "1.5px solid #eee",
                  borderRadius: 10,
                  background: "#f9fafd",
                  boxShadow: "0 2px 8px #0001",
                  textAlign: "center",
                  margin: "0 2px",
                  boxSizing: "border-box",
                }}
              >
                <div style={{
                  fontWeight: 500,
                  color: idx % 2 === 0 ? "#1976d2" : "#a06d2d",
                  fontSize: 17,
                  marginBottom: 4,
                }}>
                  {player}
                  <span style={{ color: "#aaa", fontWeight: 400, fontSize: 13, marginLeft: 2 }}>
                    [{seatTeam(idx) === "A" ? "A" : "B"}]
                  </span>
                </div>
                {/* Overlap Stack: absolutely position cards inside container */}
                <div
                  style={{
                    width: boxWidth,
                    height: 52,
                    margin: "0 auto 8px auto",
                    position: "relative",
                    background: "#fafbfc",
                    borderRadius: 6,
                    boxSizing: "border-box",
                  }}
                >
                  {Array.from({ length: cardCount }).map((_, i) => (
                    <img
                      key={i}
                      src={process.env.PUBLIC_URL + `/cards/back_${settings.cardBack?.[0] || "r"}.svg`}
                      alt="Back"
                      style={{
                        width: maxCardWidth,
                        height: 52,
                        position: "absolute",
                        left: i * (boxWidth - maxCardWidth) / Math.max(cardCount - 1, 1),
                        top: 0,
                        borderRadius: 5,
                        border: "1px solid #aaa",
                        boxShadow: "0 1px 4px #0001",
                        background: "#eee",
                        zIndex: i,
                        transition: "left 0.16s cubic-bezier(.8,.3,.3,1)",
                        pointerEvents: "none"
                      }}
                    />
                  ))}
                </div>
                {/* Optional card count, as per setting */}
                {settings.showCardCount && (
                  <div style={{
                    fontSize: 13,
                    color: "#657",
                    fontWeight: 500,
                    letterSpacing: "0.5px",
                    marginTop: 2,
                    background: "#fff6",
                    borderRadius: 6,
                    padding: "2px 7px",
                    display: "inline-block"
                  }}>
                    Cards: {cardCount}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <h3>Current turn: <span style={{ color: yourTurn ? "#0048ab" : undefined }}>{currentPlayer}</span></h3>
        {/* Last play area */}
        <div
          style={{
            margin: "0 auto 48px auto",
            width: "100%",
            maxWidth: "900px",
            minWidth: 240,
            transition: "max-width 0.2s",
          }}
        >
          <div
            style={{
              background: "#f6f8fa",
              borderRadius: 15,
              border: "1.5px solid #e2e7ef",
              minHeight: 120,
              minWidth: 240,
              width: "100%",
              padding: "16px 2vw 12px 2vw",
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              boxShadow: "0 2px 20px #e0e3ed60",
            }}
          >
            <div style={{
              fontWeight: 700,
              fontSize: "1.23rem",
              marginBottom: 10,
              letterSpacing: "0.04em"
            }}>
              Last play:
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: "6vw",
                width: "100%",
                margin: "0 auto"
              }}
            >
              {currentPlay === null ? (
                <span style={{ color: "#999", fontSize: "1.25em" }}>None yet</span>
              ) : currentPlay.cards.length > 0 ? (
                currentPlay.cards.map((card, i) => (
                  <CardImg
                    key={card + i}
                    card={card}
                    trumpSuit={trumpSuit}
                    levelRank={levelRank}
                    wildCards={wildCards}
                    highlightWild={true}
                    highlightTrump={false}
                    style={{
                      width: "min(max(7vw,50px),92px)",   // Scales 50–92px based on vw
                      height: "min(max(9vw,72px),130px)", // Scales 72–130px based on vw
                      marginRight: 8,
                      transition: "width 0.15s, height 0.15s"
                    }}
                  />
                ))
              ) : (
                <span style={{ fontSize: 23, color: "#c62a41" }}>Pass</span>
              )}
            </div>
            <div style={{
              marginTop: 9,
              fontSize: "1.08rem",
              color: "#384060",
              minHeight: 24,
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}>
              {currentPlay && currentPlay.cards.length > 0 && lastPlayType && (
                <span style={{
                  color: "#317cff",
                  fontWeight: "bold",
                  marginRight: 8
                }}>
                  {handTypeLabelString(lastPlayType)}
                </span>
              )}
              {currentPlay && currentPlay.player && (
                <span style={{
                  color: "#444",
                  fontWeight: 400,
                  marginLeft: 3
                }}>
                  by {currentPlay.player}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* === DRAG & DROP PLAYER HAND === */}
        <h3>Your hand:</h3>
        <DndContext
          sensors={sensors} // <-- use the sensors variable created at top-level, never in JSX!
          collisionDetection={closestCenter}
          // When a card is dropped, update the hand order state
          onDragEnd={({ active, over }) => {
            if (active.id !== over?.id) {
              // Find the indexes of the dragged card and the card it was dropped on
              const oldIdx = handOrder.findIndex((c, i) => (c + i) === active.id);
              const newIdx = handOrder.findIndex((c, i) => (c + i) === over.id);
              // Use dnd-kit util to move the card in the array
              setHandOrder(arrayMove(handOrder, oldIdx, newIdx));
            }
          }}
        >
          {/* This context enables cards to be sortable horizontally */}
          <SortableContext
            items={handOrder.map((c, i) => c + i)} // Every card has a unique ID (card+idx)
            strategy={horizontalListSortingStrategy}
          >
            {/* The visible row of cards */}
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                overflowX: "auto",
                overflowY: "hidden",
                whiteSpace: "nowrap",
                justifyContent: "center",
                paddingBottom: 16,
                minHeight: 80,
                margin: "0 auto",
                maxWidth: "100vw"
              }}
            >
              {handOrder.map((card, idx) => {
                const cardKey = `${card}-${idx}`;
                const isSelected = selectedCards.some(
                  sel => sel.card === card && sel.idx === idx
                );
                return (
                  <SortableCard
                    key={cardKey}
                    card={card}
                    idx={idx}
                    trumpSuit={trumpSuit}
                    levelRank={levelRank}
                    wildCards={wildCards}
                    highlightWild={!!settings.highlightWilds}
                    highlightTrump={false}
                    isSelected={isSelected}
                    onClick={() => {
                      if (!isSelected) {
                        setSelectedCards([...selectedCards, { card, idx }]);
                      } else {
                        setSelectedCards(selectedCards.filter(
                          sel => !(sel.card === card && sel.idx === idx)
                        ));
                      }
                    }}
                    style={{
                      width: 50,
                      height: 70,
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
          </SortableContext>
        </DndContext>

        {/* Play/pass/end round controls */}
        {yourTurn && (
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              justifyContent: "center",
              gap: 14,
              marginBottom: 32,
              marginTop: 12
            }}
          >
            {/* Only show Play Selected if End Round is NOT possible */}
            {!canEndRound && (
              <button
                disabled={selectedCards.length === 0}
                onClick={playSelectedCards}
                style={{
                  minWidth: 110,
                  padding: "10px 24px",
                  borderRadius: 6,
                  fontWeight: 500
                }}
              >
                Play Selected
              </button>
            )}
            {canEndRound ? (
              <button
                style={{
                  background: "#28a745",
                  color: "#fff",
                  minWidth: 110,
                  padding: "10px 24px",
                  fontSize: "1rem",
                  borderRadius: 6,
                  fontWeight: 500
                }}
                onClick={endRound}
              >
                End Round
              </button>
            ) : (
              <button
                onClick={passTurn}
                style={{
                  minWidth: 80,
                  padding: "10px 24px",
                  borderRadius: 6,
                  fontWeight: 500
                }}
              >
                Pass
              </button>
            )}
          </div>
        )}

        {!yourTurn && !canEndRound && (
          <p style={{ margin: "18px 0 32px 0" }}>
            Waiting for <strong>{currentPlayer}</strong> to play...
          </p>
        )}
      </div>
    );
  }

  // ---- 4. LANDING/Lobby screen ----
  return (
    <div>
      <h1 style={{ textAlign: "center" }}>Guan Dan Web Game</h1>
      <h3 style={{ textAlign: "center", color: connected ? "green" : "red" }}>
        Server Status: {connected ? "🟢 Connected" : "🔴 Disconnected"}
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
function CardImg({ card, trumpSuit, levelRank, wildCards, onClick, highlightWild, style, isSelected }) {
  const wild = isWild(card, levelRank, trumpSuit, wildCards);
  let borderStyle;
  if (isSelected) {
    borderStyle = "3px solid #005fff";
  } else if (highlightWild && wild) {
    borderStyle = "3px solid #9e3ad7";
  } else {
    borderStyle = "1.5px solid #aaa";
  }

  return (
    <img
      src={process.env.PUBLIC_URL + `/cards/${card}.svg`}
      alt={card}
      onClick={onClick}
      style={{
        border: borderStyle,
        background: highlightWild && wild ? "#f8eafd" : (card === "JoB" || card === "JoR") ? "#f6f5ee" : "#fff",
        borderRadius: 10,
        boxShadow: isSelected
          ? "0 0 8px #005fff88"
          : highlightWild && wild
          ? "0 0 18px #9e3ad7"
          : undefined,
        ...style
      }}
      title={wild ? "Wild Card" : ""}
    />
  );
}

function TributeOverlay({ tributeState, setTributeState, socket, playerName, hands }) {
  if (!tributeState) return null;
  const { tributes, tribute_cards = {}, exchange_cards = {}, step } = tributeState;
  const myHand = hands && playerName ? hands[playerName] : [];

  // Tribute payment step
  if (step === 'pay') {
    const myTribute = tributes && tributes.find(t => t.from === playerName);
    if (myTribute && !tribute_cards[playerName]) {
      return (
        <div className="tribute-modal">
          <h3>You must pay tribute to {myTribute.to}</h3>
          <p>Select your highest card that is not a wild (see rules)</p>
          <div>
            {myHand.map(card => (
              <button key={card} onClick={() => {
                socket.emit('pay_tribute', { roomId: tributeState.roomId, from: playerName, card });
              }}>{card}</button>
            ))}
          </div>
        </div>
      );
    } else {
      return <div className="tribute-modal">Waiting for all tributes...</div>;
    }
  }

  // Return step (winners return a card to the tribute-payer)
  if (step === 'return') {
    const myReturn = tributes && tributes.find(t => t.to === playerName);
    if (myReturn && !exchange_cards[playerName]) {
      return (
        <div className="tribute-modal">
          <h3>You must return a card to {myReturn.from}</h3>
          <p>Select any card (not the one just received from tribute)</p>
          <div>
            {myHand.map(card => (
              <button key={card} onClick={() => {
                socket.emit('return_tribute', { roomId: tributeState.roomId, from: playerName, to: myReturn.from, card });
              }}>{card}</button>
            ))}
          </div>
        </div>
      );
    } else {
      return <div className="tribute-modal">Waiting for all tribute returns...</div>;
    }
  }

  // Done
  if (step === 'done') {
    return <div className="tribute-modal">Tribute complete! Dealing new cards...</div>;
  }

  // Default
  return null;
}



