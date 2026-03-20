const express = require('express')
const router = express.Router()
const groupController = require('../../controllers/Admin/group.controller')
const promptController = require('../../controllers/Admin/promt.controller')
router.post('/create',groupController.create)
router.get('/list',groupController.getAllGroup)
router.post('/prompt/create',promptController.create)

module.exports =router