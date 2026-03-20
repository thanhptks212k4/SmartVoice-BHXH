
const redis = require('../../services/redisService')
const uploadfile = async (req,res)=>{
 
    try {
        const userId = req.user.id
        const files = req.files
        const groupId = req.body.groupId
        const base = "yes"

        if (!userId) return res.status(400).json({ success: false, message: 'Thiếu userId!' });
        if (!files || files.length === 0)
        return res.status(400).json({ success: false, message: 'Chưa chọn file nào!' });
        

        const job ={
            userId,
            groupId,
            base
        }

        await redis.pushEmbeddingTask(job)
        console.log(`[UPLOAD BATCH] User: ${userId} vừa upload ${files.length} file. Đã đẩy 1 task vào Redis.`);

        return res.status(200).json({
            success:true,
            message:'upload thanh cong base , dang bat dau huan luyen',
            userId,
            files: files.map(f => ({
            filename: f.filename,
            path: f.path,
            size: f.size
            }))
        })

    } catch (error) {
        console.error('🔥 Lỗi upload:', error);
        res.status(500).json({ success: false, message: 'Internal Server Error', error: error.message });
  }

}





module.exports = {uploadfile}