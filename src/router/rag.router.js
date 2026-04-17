const express = require('express');
const router = express.Router();
const {verifyToken} = require("../middlewares/authAPI.middleware"); 
const upload = require("../config/multer.config")
const ragController = require('../controllers/client/rag.controller');  // dùng client controller đã có groupId + base

router.post('/uploadfile', verifyToken, upload.array('files', 10), ragController.uploadfile);

module.exports = router;
