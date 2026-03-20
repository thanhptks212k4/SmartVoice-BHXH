require('dotenv').config();
module.exports = {
    PORT: process.env.PORT,
    AUTH_TOKEN: process.env.AUTH_TOKEN,
    LLM: process.env.API_LLM,
    HOST_DB: process.env.HOST_DB,
    NAME_DB: process.env.NAME_DB,
    USER_DB: process.env.USER_DB,
    PASS_DB: process.env.PASS_DB,
    POST_REDIS: process.env.POSST_REDIS,
    HOST_REDIS: process.env.HOST_REDIS,
    PASS_REDIS: process.env.PASS_REDIS
}