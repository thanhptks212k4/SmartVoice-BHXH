const User = require('../model/user.model');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const config = require('../config/server');

// ĐĂNG KÝ
const register = async (req, res) => {
    try {
        const { username, password } = req.body;
        const existingUser = await User.findOne({ where: { username } });
        if (existingUser) {
            return res.status(400).json({ success: false, message: 'User đã tồn tại!' });
        }
        const salt = await bcrypt.genSalt(10);
        // console.log(password)
        const hashedPassword = await bcrypt.hash(password, salt);
        // console.log(hashedPassword)
        const newUser = await User.create({
            username: username,
            password: hashedPassword
        });

        res.status(201).json({
            success: true,
            message: 'Đăng ký thành công!',
            data: { id: newUser.id, username: newUser.username }
        });
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};


const login = async (req, res) => {
    try {
        const { username, password } = req.body;


        const user = await User.findOne({ where: { username } });
        if (!user) {
            return res.status(404).json({ success: false, message: 'Người dùng không tồn tại!' });
        }


        const isMatch = await bcrypt.compare(password, user.password);
        if (!isMatch) {
            return res.status(401).json({ success: false, message: 'Sai mật khẩu' });
        }


        const token = jwt.sign(
            { id: user.id, username: user.username },
            config.AUTH_TOKEN || 'supersecret',
            { expiresIn: '30d' } // Login 1 lần dùng 30 ngày
        );

        res.json({
            success: true,
            message: 'Đăng nhập thành công!',
            token: token
        });
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};

module.exports = { register, login };