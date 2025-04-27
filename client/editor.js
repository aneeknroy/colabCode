import { createSocket } from './websocket.js';

const editor = CodeMirror(document.getElementById("editor"), {
  lineNumbers: true,
  mode: "javascript"
});

const roomId = "default-room";
const socket = createSocket(roomId, handleMessage);

function handleMessage(data) {
  if (data.type === "edit") {
    editor.replaceRange(data.text, data.from, data.to, "remote");
  }

  if (data.type === "user_list") {
    const ul = document.getElementById("user-list");
    ul.innerHTML = "";
    data.users.forEach(user => {
      const li = document.createElement("li");
      li.textContent = user;
      ul.appendChild(li);
    });
  }
}

editor.on("change", (instance, change) => {
  if (change.origin !== "remote") {
    socket.send(JSON.stringify({
      type: "edit",
      text: change.text,
      from: change.from,
      to: change.to
    }));
  }
});

editor.on("cursorActivity", () => {
  const cursor = editor.getCursor();
  socket.send(JSON.stringify({
    type: "cursor",
    cursor: cursor
  }));
});
