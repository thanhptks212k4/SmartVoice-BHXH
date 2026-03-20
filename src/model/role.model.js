const {DataTypes, INTEGER} = require('sequelize')
const sequelize  = require('../config/db')

const Role = sequelize.define("Role",{
    roleid:{
        type: DataTypes.INTEGER,
        primaryKey: true,
        allowNull:false
    },
    rolename:{
        type: DataTypes.STRING,
        allowNull:false
    }
},
{
    timestamps:false,
    tableName:"Role"
})

module.exports = Role