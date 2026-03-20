const redisService = require('../services/redisService');
const User = require('../model/user.model')
const Prompt = require('../model/group_prompt.model')
const handleChatSocket = (wss) => {
    redisService.listenForResponses((userId, data) => {

        wss.clients.forEach((client) => {

            if (client.readyState === 1 && client.user && String(client.user.id) === String(userId)) {
                client.send(JSON.stringify({
                    type: 'AI_VOICE_REPLY',
                    text: data.text,
                    audioUrl: data.audioUrl,
                    // userId: userId
                }));
                // console.log(`[Socket] Đã gửi link voice tới user: ${userId}`);
            }
        });
    });
// client kết nối ws đến server 
    wss.on('connection', async (ws, req) => {
        const user = req.user;
        // tìm user này thuộc group nào 
        const userGroup = await User.findOne({
        where:{
            id:user.id,
        }
        })
        const groupId = userGroup.groupId
        // nếu không có thoong tin user thì từ chối
        if (!user || !user.id) {
            console.log("Kết nối bị từ chối: Không có thông tin User");
            ws.close();
            return;
        }

        ws.user = user;
        const cacheKey = `group:${groupId}:content`;
        let content = await redisService.getCache(cacheKey)
        if (content) {
         console.log(`[Cache HIT] group ${groupId}`);
        }else{
            const promptGroup = await Prompt.findOne({
            where:{
                groupId:groupId
            }
        })
        if (promptGroup) {
            content = promptGroup.content 
        } else {
            console.warn(`[Cảnh báo] Group ${groupId} chưa có Prompt! Đang dùng prompt mặc định.`);
            content = "Bạn là trợ lý ảo thân thiện thông minh.";
        }
        await redisService.setCache(cacheKey, content, 3600);
        console.log(`[Cache MISS] group ${groupId} → đã lưu cache`);
        }
        console.log(`[Socket] ${user.username} đã kết nối.`);


        ws.on('message', async (message) => {
            try {
                const msgString = message.toString();
                const payload = JSON.parse(msgString);

                const task = {
                    userId: user.id,
                    groupId:groupId,
                    text: payload.text,
                    voice:payload.voice,
                    language: payload.language || 'vi',
                    timestamp: Date.now()
                };

                await redisService.pushTask(task);

                ws.send(JSON.stringify({
                    type: 'STATUS',
                    content: 'Hệ thống đang sinh giọng nói...'
                }));

            } catch (err) {
                console.error("Lỗi xử lý tin nhắn:", err.message);
                ws.send(JSON.stringify({ type: 'ERROR', content: 'Lỗi xử lý yêu cầu' }));
            }
        });

        ws.on('close', async () => {console.log(`${user.username} ngắt kết nối.`);
            const task = {
                    userId: user.id,
                    text:"disconectuser",
                    timestamp: Date.now()
                };
        await redisService.pushTask(task)
        });
        
    });
};

module.exports = handleChatSocket;