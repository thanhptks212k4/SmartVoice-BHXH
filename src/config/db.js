const {Sequelize} = require('sequelize')
const server_config = require("../config/server")


const sequelize = new Sequelize(server_config.NAME_DB,server_config.USER_DB,server_config.PASS_DB,{
    host: server_config.HOST_DB,
    dialect: 'postgres',
    logging: false,
})
module.exports = sequelize;