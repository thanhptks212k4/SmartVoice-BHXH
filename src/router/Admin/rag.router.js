const express = require('express')
const router =express.Router()
const ragController = require('../../controllers/Admin/rag.controller')
const upload = require("../../config/multer.config")
router.post('/uploadfile',upload.array('files',10000),ragController.uploadfile)
module.exports = router