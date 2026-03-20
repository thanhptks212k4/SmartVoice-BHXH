const {DataTypes} = require('sequelize')
const sequelize = require('../config/db')

const Group = sequelize.define("Group",{
    groupId:{
        type:DataTypes.UUID,
        defaultValue:DataTypes.UUIDV4,
        primaryKey:true,
        allowNull:false
    },
    groupName:{
        type:DataTypes.STRING,
        allowNull:false,
        unique:true
    },
    email:{
        type:DataTypes.STRING,
        allowNull:true,
        unique:true,
        validate:{
            isEmail:true
        }
    },
    phoneNumber:{
        type:DataTypes.STRING(15),
        allowNull:true,
        unique:true,
        validate:{
            is: /^[0-9]+$/i, 
            len: [10, 15]
        }
    }
},
{
    tableName: 'Groups',
    timestamps: true
})

module.exports = Group ;