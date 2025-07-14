import React, { useState } from "react";

function CreateJoinRoom({ onCreateRoom, onJoinRoom }) {
  const [username, setUsername] = useState("");
  const [roomId, setRoomId] = useState("");

  return (
    <div style={{ textAlign: "center", marginTop: "4rem" }}>
      <h2>Guan Dan Game Lobby</h2>
      <div style={{ margin: "2rem 0" }}>
        <input
          type="text"
          placeholder="Your name"
          value={username}
          onChange={e => setUsername(e.target.value)}
          style={{ padding: 8, fontSize: 16, marginBottom: 10 }}
        />
        <br />
        <button
          style={{ marginTop: 10, padding: "8px 20px", fontSize: 16 }}
          onClick={() => {
            if (username.trim()) {
              onCreateRoom({ username });
            } else {
              alert("Please enter your name.");
            }
          }}
        >
          Create Room
        </button>
      </div>
      <div style={{ margin: "2rem 0" }}>
        <h3>Join a Room</h3>
        <input
          type="text"
          placeholder="Room ID"
          value={roomId}
          onChange={e => setRoomId(e.target.value)}
          style={{ padding: 8, fontSize: 16 }}
        />
        <br />
        <button
          style={{ marginTop: 10, padding: "8px 20px", fontSize: 16 }}
          onClick={() => {
            if (username.trim() && roomId.trim()) {
              onJoinRoom({ username, roomId });
            } else {
              alert("Please enter both your name and a room ID.");
            }
          }}
        >
          Join Room
        </button>
      </div>
    </div>
  );
}

export default CreateJoinRoom;
