const Redis = require('ioredis')
const config = require("../config/server")


const redisPublisher = new Redis({
    host: config.HOST_REDIS,
    port: config.PORT_REDIS,
    password: config.PASS_REDIS
})

const redisSubscriber = new Redis({
    host: config.HOST_REDIS,
    port: config.PORT_REDIS,
    password: config.PASS_REDIS
})

class RedisService {
    constructor() {
        this.queueName = 'ai_tasks';
        // this.responseChannel = 'ai_responses';
        this.embeddingQueue = 'embedding_tasks';
        this.embeddingResponseChannel = 'embedding_responses';
        this.voiceResponsePattern = 'voice_ready:*';
        this.initPatternListener();
    }
    // tts_task 
    async pushTTSTask(task){
        try {
            const data = JSON.stringify(task)
            await redisPublisher.lpush(this.ttsQueue, data);
        } catch (err) {
            console.error('[Redis] lỗi push TTS task ' , err)
            throw err
        }
    }
   

    initPatternListener() {
        redisSubscriber.on('pmessage', (pattern, channel, message) => {
            try {
                const data = JSON.parse(message);

                if (pattern === this.voiceResponsePattern) {
                    const userId = channel.split(':')[1];
                    // console.log(`[Redis] 🎤 Audio ready for User: ${userId}`);
                    if (this.voiceCallback) this.voiceCallback(userId, data);
                }

                // else if (pattern === this.embeddingResponsePattern) {
                //     const userId = channel.split(':')[1];
                //     console.log(`[Redis] 🧠 Embedding done for User: ${userId}`);
                //     if (this.embeddingCallback) this.embeddingCallback(userId, data);
                // }
            } catch (err) {
                console.error('[Redis] Lỗi parse JSON:', err);
            }
        });
    }


    listenForResponses(callback) {
        this.voiceCallback = callback;
        redisSubscriber.psubscribe(this.voiceResponsePattern);
        console.log(`[Redis] Đang nghe Pattern: ${this.voiceResponsePattern}`);
    }

    // ai task
    async pushTask(task) {
        try {
            const data = JSON.stringify(task)
            await redisPublisher.lpush(this.queueName, data);
        } catch (err) {
            console.error('[Redis] lỗi push task ', err)
            throw err
        }
    }
    // listenForResponses(callback) {
    //     redisSubscriber.subscribe(this.responseChannel);

    //     redisSubscriber.on('message', (channel, message) => {
    //         if (channel === this.responseChannel) {
    //             const data = JSON.parse(message);
    //             console.log(data)
    //             callback(data);
    //         }
    //     });
    // }

    // embetding task 
    async pushEmbeddingTask(task) {
        try {
            const data = JSON.stringify(task);
            await redisPublisher.lpush(this.embeddingQueue, data);
        } catch (err) {
            console.error('[Redis] lỗi push embedding task', err);
            throw err;
        }
    }

    listenForEmbeddingResponses(callback) {
        redisSubscriber.subscribe(this.embeddingResponseChannel);
        redisSubscriber.on('message', (channel, message) => {
            if (channel === this.embeddingResponseChannel) {
                const data = JSON.parse(message);
                callback(data);
            }
        });
    }
// cache 

    async getCache(key){
        const data = await redisPublisher.get(key)
        return data || null 
    }

    async setCache(key,value,ttl =3600){
        await redisPublisher.set(key,value,'EX',ttl)
    }
    async delCache(key) {
        await redisPublisher.del(key);
        console.log(`[Cache] Đã xóa key: ${key}`);
    }

    // end cache redis 
}

module.exports = new RedisService();