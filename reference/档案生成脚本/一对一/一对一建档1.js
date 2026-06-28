module.exports = async () => {

    try {

        // ========= 1. 获取用户输入 =========

        const studentName = await app.plugins.plugins.quickadd.api.inputPrompt("请输入学员姓名");
        if (!studentName) throw new Error("学员姓名不能为空");

        // ========= 首课日期 =========
        const firstDate = await app.plugins.plugins.quickadd.api.datePrompt(
            "请选择首课日期",
            "YYYY-MM-DD"
        );

        if (!firstDate) throw new Error("首课日期不能为空");

        // ========= 首课时间 =========
        const timeOptions = ["10:00", "12:20", "15:30", "17:50", "20:10"];

        const firstTime = await app.plugins.plugins.quickadd.api.suggester(
            timeOptions,
            timeOptions,
            false,
            "请选择首课时间"
        );

        if (!firstTime) throw new Error("必须选择首课时间");

        const firstClassDate = `${firstDate} ${firstTime}`;

        // 上课频率选择
        const scheduleOptions = ["weekend (周末班)", "full-time (全日制)"];
        const scheduleRaw = await app.plugins.plugins.quickadd.api.suggester(
            scheduleOptions,
            scheduleOptions,
            false,
            "请选择上课频率"
        );
        if (!scheduleRaw) throw new Error("未选择上课频率");
        const scheduleType = scheduleRaw.split(" ")[0]; // 提取英文值

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

        const curriculumTags = [courseType];

        // 选择存放根目录
        const allFolders = app.vault.getAllLoadedFiles()
            .filter(f => f.children)
            .map(f => f.path)
            .filter(p => p !== "")
            .sort();
        
        const folderOptions = ["(根目录)", ...allFolders];
        const selectedPath = await app.plugins.plugins.quickadd.api.suggester(
            folderOptions,
            folderOptions,
            false,
            "请选择学员档案存放位置"
        );
        if (!selectedPath) throw new Error("未选择存放位置");

        const basePath = selectedPath === "(根目录)" ? "" : selectedPath;

        // ========= 2. 构建路径与文件名 =========

        const studentFolderName = studentName;
        const studentFolderPath = basePath ? `${basePath}/${studentFolderName}` : studentFolderName;
        const archiveFileName = `${studentName}.md`;
        const archiveFilePath = `${studentFolderPath}/${archiveFileName}`;

        // ========= 3. 创建文件夹 =========

        // 检查文件夹是否存在，不存在则创建
        let studentFolder = app.vault.getAbstractFileByPath(studentFolderPath);
        if (!studentFolder) {
            await app.vault.createFolder(studentFolderPath);
            new Notice(`已创建学员档案夹：${studentFolderPath}`);
        } else {
            if (!confirm(`文件夹 "${studentFolderPath}" 已存在，是否继续写入档案页？\n(点击取消则停止)`)) {
                throw new Error("用户取消操作");
            }
        }

        // ========= 4. 生成档案页内容 =========

        const startDate = firstDate;
        
        // 构建 Frontmatter
        const tagsArray = ["#学员档案", "#一对一", ...curriculumTags.map(tag => `#${tag}`)];
        
        const frontmatter = `---
first_class_date: ${firstClassDate}
status: "active"
schedule_type: "${scheduleType}"
total_lessons: 0
tags:
${tagsArray.map(tag => `  - "${tag}"`).join('\n')}
---
`;

        // 构建正文
        let bodyContent = `## 📚 课程索引

`;

        // 为每个 Tag 生成区块
        for (const tag of curriculumTags) {
            bodyContent += `### 🏷️ ${tag}
- *暂无课程记录，等待生成第 1 课...*

---

`;
        }

        bodyContent += `
## 📈 成长轨迹 (手动记录)
- **${startDate}**: 档案建立。


---

## 📋 测试反馈

## 📝 备注
`;

        const fullContent = frontmatter + bodyContent;

        // ========= 5. 写入文件 =========

        // 检查文件是否存在
        const existingFile = app.vault.getAbstractFileByPath(archiveFilePath);
        if (existingFile) {
            // 如果存在，覆盖内容
            await app.vault.modify(existingFile, fullContent);
            new Notice(`已更新档案页：${archiveFilePath}`);
        } else {
            // 不存在，创建
            await app.vault.create(archiveFilePath, fullContent);
            new Notice(`已创建档案页：${archiveFilePath}`);
        }

        // ========= 6. 打开档案页 =========

        const file = app.vault.getAbstractFileByPath(archiveFilePath);
        if (file) app.workspace.getLeaf().openFile(file);

    } catch (err) {
        console.error("One-on-One Archive Setup Error:", err);
        new Notice(`❌ 建档失败：${err.message}`);
    }
};