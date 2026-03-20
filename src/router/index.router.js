const auth = require('./auth.router')
const rag = require('./rag.router')
const admin = require("./Admin/index.router")
const client = require('./Client/index.router')
module.exports = (app) => {
  app.use("/auth",auth)
  app.use("/rag",rag)
  app.use("/api/admin",admin)
  app.use('/api/',client)


}