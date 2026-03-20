require('dotenv').config();
const express = require('express');
const WebSocket = require('ws');
const http = require('http');
const {sequelize} = require('./model/index');
const serverConfig = require('./config/server');

const handleChatSocket = require('./sockets/chat.socket');
const { veryConnection } = require('./middlewares/auth.middleware');

const app = express();
const server = http.createServer(app);

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Router API
const router = require("./router/index.router");
router(app);

// WebSocket setup
const wss = new WebSocket.Server({
  server,
  verifyClient: veryConnection
});

// Kích hoạt logic socket
handleChatSocket(wss);

// Error Handling
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ success: false, message: 'Internal Server Error' });
});

// Database & Server Listen
sequelize
  .authenticate()
  .then(() => {
    console.log(' Kết nối database thành công!');
    return sequelize.sync({ alter: true });
  })
  .then(() => {
    const PORT = serverConfig.PORT || 3000;
    server.listen(PORT, () => {
      console.log(` Server đang chạy tại http://localhost:${PORT}`);
    });
  })
  .catch((err) => {
    console.error(' Lỗi khởi động:', err.message);
    process.exit(1);
  });