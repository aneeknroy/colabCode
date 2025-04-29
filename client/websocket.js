export function createSocket(roomId, onMessageCallback) {
  const socket = new WebSocket(`ws://localhost:6789/${roomId}`);

  socket.onopen = () => {
    console.log("Connected to room:", roomId);
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessageCallback(data);
  };

  socket.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  socket.onclose = () => {
    console.warn("WebSocket closed");
  };

  return socket;
}
