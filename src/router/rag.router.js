const express = require('express');
const router = express.Router();
const ragController = require('../controllers/rag.controller');
const {verifyToken} = require("../middlewares/authAPI.middleware"); 
const upload = require("../config/multer.config")


router.post('/uploadfile', verifyToken ,upload.array('files', 10) ,ragController.uploadfile);

module.exports = router;