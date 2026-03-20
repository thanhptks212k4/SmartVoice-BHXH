// ✅ src/middlewares/auth.middleware.js
const config = require('../config/server');
const jwt = require('jsonwebtoken');
const User = require('../model/user.model')
const Role = require ("../model/role.model")
// danhf cho http
const verifyToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  if (!authHeader)
    return res.status(401).json({ message: 'Thiếu token' });

  const token = authHeader.split(' ')[1];
  try {
    const decoded = jwt.verify(token, config.AUTH_TOKEN);
    req.user = decoded;
    next();
  } catch (err) {
    return res.status(403).json({ message: 'Token không hợp lệ hoặc đã hết hạn' });
  }
};

const isAdmin = async (req, res, next) => {
  if (!req.user)
    return res.status(401).json({ message: "User chưa xác thực" });

  const user = await User.findByPk(req.user.id, {
    include: Role
  });

  const userRole = user.Role.rolename;

  if (userRole === "admin") {
    return next(); 
  }

  // Nếu không phải admin, dòng này mới được chạy
  return res.status(403).json({ message: "Hãy liên hệ với admin" });
};

module.exports = {verifyToken , isAdmin};