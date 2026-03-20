
const Prompt = require('../../model/group_prompt.model')
const create = async (req,res)=>{
  try {
        const {groupId , promptName ,content} = req.body
        const existPromt = await Prompt.findOne({
            where:{
                groupId:groupId
            }
        })
        // console.log(existPromt)
        if(existPromt){
            return res.status(400).json({
                success:false,
                message:"user này đã có prompt rồi "
            })
        }

        const newPrompt = await Prompt.create({
                groupId,
                promptName,
                content
            });

            return res.status(201).json({
                success: true,
                data: newPrompt
            });

  } catch (error) {
        return res.status(500).json({
            success:false,
            message:error.message
        })
  }

}

module.exports = {create}