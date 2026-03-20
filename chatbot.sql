INSERT INTO "Role" (roleid, rolename)
VALUES (1, 'admin'), (2, 'user')
ON CONFLICT (roleid) DO NOTHING;

INSERT INTO
    "Groups" (
        "groupId",
        "groupName",
        "email",
        "phoneNumber",
        "createdAt",
        "updatedAt"
    )
VALUES (
        gen_random_uuid (),
        'admin',
        'admin@admin.vn',
        '0987654321',
        now(),
        now()
    );

INSERT INTO
    "Users" (
        id,
        roleid,
        "groupId",
        username,
        password,
        "createdAt",
        "updatedAt"
    )
VALUES (
        gen_random_uuid (),
        1,
        '4551d2a4-e1a1-4809-811f-6710a8aaf7ba',
        'admin',
        '$2a$10$gOykdfM8WPHnTymyCahCaOelCcKdgVYbRoBs3uMFgH8hx9GTIX2G2',
        now(),
        now()
    )