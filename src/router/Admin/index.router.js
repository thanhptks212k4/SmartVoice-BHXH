const express = require('express')
const router = express.Router()
const {verifyToken ,isAdmin} = require('../../middlewares/authAPI.middleware')
const user = require('./user.router')
const group = require('./group.router')
const rag = require('./rag.router')
router.use(verifyToken,isAdmin)


router.use('/user' ,user)
router.use('/group',group)
router.use('/rag',rag)

module.exports = router