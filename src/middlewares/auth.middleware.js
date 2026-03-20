const config = require('../config/server')
const jwt = require('jsonwebtoken')
// danhf cho ws 
const veryConnection = (info, cb) => {
    const url = new URL(info.req.url, `http://${info.req.headers.host}`);
    const token = url.searchParams.get('token');

    if (!token) {
        console.log(" Từ chối kết nối: Không tìm thấy Token.");
        return cb(false, 401, 'Unauthorized');
    }

    try {
        // Giải mã token
        const decoded = jwt.verify(token, config.AUTH_TOKEN);
        console.log(decoded)

        info.req.user = decoded;

        cb(true);

    } catch (err) {
        console.log("❌ Token không hợp lệ hoặc đã hết hạn.");
        cb(false, 401, "Unauthorized");
    }
}

module.exports = { veryConnection };