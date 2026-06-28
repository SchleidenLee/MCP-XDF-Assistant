module.exports = async () => {
    try {

        // ========= 获取班级名称 =========
        const className = await app.plugins.plugins.quickadd.api.inputPrompt("请输入班级名称（如：G3-01班）");
        if (!className) throw new Error("班级名称不能为空");

        // ========= 首课日期 =========
        const firstDate = await app.plugins.plugins.quickadd.api.datePrompt(
            "请选择首课日期",
            "YYYY-MM-DD"
        );

        if (!firstDate) throw new Error("首课日期不能为空");

        // ========= 首课时间 =========
        const timeOptions = ["10:00", "12:20", "15:30", "17:50"];

        const firstTime = await app.plugins.plugins.quickadd.api.suggester(
            timeOptions,
            timeOptions,
            false,
            "请选择首课时间"
        );

        if (!firstTime) throw new Error("必须选择首课时间");

        const firstClassTime = `${firstDate} ${firstTime}`;

        // ========= 班级类型 (schedule_type) =========
        const classTypeOptions = ["weekend (周末班)", "full-time (全日制)"];

        const classTypeRaw = await app.plugins.plugins.quickadd.api.suggester(
            classTypeOptions,
            classTypeOptions,
            false,
            "请选择班级类型"
        );

        if (!classTypeRaw) throw new Error("必须选择班级类型");

        const scheduleType = classTypeRaw.split(" ")[0]; // 提取英文值

        // ========= 课程体系选择 =========
        const courseOptions = [
            "Foundation Grammar",
            "L1教材",
            "L1讲义",
            "L2教材",
            "L2讲义",
            "精讲精练"
        ];

        const courseType = await app.plugins.plugins.quickadd.api.suggester(
            courseOptions,
            courseOptions,
            false,
            "请选择课程体系"
        );

        if (!courseType) throw new Error("必须选择课程体系");


        // ========= 学员名单 =========
        const studentListInput = await app.plugins.plugins.quickadd.api.inputPrompt(
            "请输入学员名单（用空格分隔）\n例如：张三 李四 王五",
            "张三 李四"
        );

        if (!studentListInput) throw new Error("学员名单不能为空");

        const students = studentListInput
            .split(/\s+/)
            .map(name => name.trim())
            .filter(name => name !== "");


        // ========= 选择存放位置 =========
        const allFolders = app.vault.getAllLoadedFiles()
            .filter(f => f.children)
            .map(f => f.path)
            .filter(p => p !== "")
            .sort();

        const folderOptions = ["(根目录)", ...allFolders];

        const selected = await app.plugins.plugins.quickadd.api.suggester(
            folderOptions,
            folderOptions,
            false,
            "请选择存放班级文件夹的位置"
        );

        if (!selected) throw new Error("未选择文件夹");

        const userPath = selected === "(根目录)" ? "" : selected;


        // ========= 创建班级文件夹 =========
        const classFolderPath = userPath ? `${userPath}/${className}` : className;

        let classFolder = app.vault.getAbstractFileByPath(classFolderPath);

        if (!classFolder) {
            await app.vault.createFolder(classFolderPath);
            new Notice(`📁 班级文件夹 "${className}" 已创建`);
        } else {
            new Notice(`📁 班级文件夹 "${className}" 已存在`);
        }


        // ========= 生成学生表 =========
        const studentRows = students.map(name => {
            return `| ${name} | | | | | | |`;
        }).join('\n');


        // ========= 生成班级主页内容 =========
        const content = `---
first_class_time: ${firstClassTime}
schedule_type: "${scheduleType}"
tags: ["#班课档案", "#${courseType}"]
status: "active"
student_count: ${students.length}
last_lesson_date: null
---

## 👥 学员名单

| 姓名 | 学校 | 年级 | 英语程度 | 目标分数 | 已上课程 | 备注 |
|------|------|------|----------|----------|----------|------|
${studentRows}

---

## 📝 班级备注
<!-- 在此记录班级注意事项 -->

---

## 📅 课程记录索引
<!-- 每次课后在这里增加课程链接 -->


---

## 📋 测试反馈

`;


        // ========= 创建班级主页 =========
        const archiveFilePath = `${classFolderPath}/${className}.md`;

        if (!app.vault.getAbstractFileByPath(archiveFilePath)) {
            await app.vault.create(archiveFilePath, content);
            new Notice(`📄 班级主页已创建`);
        }


        // ========= 打开主页 =========
        const archiveFile = app.vault.getAbstractFileByPath(archiveFilePath);

        if (archiveFile) {
            await app.workspace.getLeaf(true).openFile(archiveFile);
        }

        new Notice(`✅ 班级 "${className}" 创建完成！`);

    } catch (error) {
        new Notice(`❌ 运行失败：${error.message}`, 6000);
        console.error("QuickAdd 脚本错误:", error);
    }
};