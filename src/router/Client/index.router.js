const express = require('express')
const router =express.Router()
const {verifyToken} = require('../../middlewares/authAPI.middleware')
const upload = require('../../config/multer.config')
const ragController = require('../../controllers/client/rag.controller')
router.use(verifyToken)

router.post('/rag/uploadfile',upload.array('files', 10),ragController.uploadfile)

module.exports = router