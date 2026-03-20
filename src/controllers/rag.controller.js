const redits = require("../services/redisService")
const uploadfile = async (req, res) => {
    try {
    console.log(' Body:', req.body);
    console.log(' Files:', req.files);

    const userId = req.user.id;
    const files = req.files;

    if (!userId) return res.status(400).json({ success: false, message: 'Thiếu userId!' });
    if (!files || files.length === 0)
      return res.status(400).json({ success: false, message: 'Chưa chọn file nào!' });

    const job = {
      userId,
      createdAt: Date.now(),
      // files: files.map(f => ({
      //   filename: f.filename,
      //   path: f.path,
      //   size: f.size
      // }))
    };

    // Gửi 1 job duy nhất vào Redis
    await redits.pushEmbeddingTask(job)

    res.json({
      success: true,
      message: 'Upload thành công! , đang bắt đầu huấn luyện',
      userId,
      files: files.map(f => ({
        filename: f.filename,
        path: f.path,
        size: f.size
      }))
    });
  } catch (error) {
    console.error(' Lỗi upload:', error);
    res.status(500).json({ success: false, message: 'Internal Server Error', error: error.message });
  }
};

module.exports = { uploadfile };