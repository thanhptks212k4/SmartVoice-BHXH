
const Group = require('../../model/group.model')
const create = async(req,res)=>{

    try{
        const {groupName , email , phoneNumber} = req.body
    const existingGroupName = await Group.findOne({where:{groupName}})
    const existingEmail = await Group.findOne({where:{email}})
    const existingPhoneNumber = await Group.findOne({where:{phoneNumber}})

    if(existingGroupName){
        return res.status(400).json({ success: false, message: 'Group đã tồn tại!' });
    }
     if(existingEmail){
        return res.status(400).json({ success: false, message: 'email đã tồn tại!' });
    }
     if(existingPhoneNumber){
        return res.status(400).json({ success: false, message: 'sdt đã tồn tại!' });
    }
    const newGroup = await Group.create({
        groupName:groupName,
        email:email,
        phoneNumber:phoneNumber
    })
    res.status(200).json({
        success:true,
        message:"Tao thanh cong group ",
        data:{
            id:newGroup.groupId,
            groupName:newGroup.groupName,
            email:newGroup.eamil,
            phoneNumber:newGroup.phoneNumber
        }
    })
    }
    catch(e){
        res.status(500).json({ success: false, message: e.message });
    }
}

const getAllGroup = async (req ,res) => {
    try{
        const groups = await Group.findAll()
        return res.status(200).json({
            success:true,
            count:groups.length,
            data:groups
        })
    }
    catch(e){
        return res.status(500).json({message:"Khong lay duoc group"})
    }
}

module.exports= {create,getAllGroup}