module.exports = async () => {
    try {
        // ========= 1. 获取用户输入 =========
        const targetName = await app.plugins.plugins.quickadd.api.inputPrompt(
            "请输入班级号或学员姓名（如：3372 或 许宸睿）"
        );
        if (!targetName) throw new Error("班级号/学员名不能为空");

        const testName = await app.plugins.plugins.quickadd.api.inputPrompt(
            "请输入测试名称（如：结班测试、阶段测试1）",
            "结班测试"
        );
        if (!testName) throw new Error("测试名称不能为空");

        const testDate = await app.plugins.plugins.quickadd.api.datePrompt(
            "请选择测试日期",
            "YYYY-MM-DD"
        );
        if (!testDate) throw new Error("测试日期不能为空");

        // ========= 2. 查找档案 =========
        const allFolders = app.vault.getAllLoadedFiles()
            .filter(f => f.children)
            .map(f => f.path)
            .sort();

        // 搜索匹配的文件夹
        let targetFolder = null;
        let archiveFile = null;

        for (const folderPath of allFolders) {
            const folderName = folderPath.split("/").pop();
            if (folderName === targetName) {
                const mdPath = `${folderPath}/${targetName}.md`;
                const mdFile = app.vault.getAbstractFileByPath(mdPath);
                if (mdFile) {
                    targetFolder = app.vault.getAbstractFileByPath(folderPath);
                    archiveFile = mdFile;
                    break;
                }
            }
        }

        if (!archiveFile) throw new Error(`未找到 ${targetName} 的档案文件`);

        // ========= 3. 读取内容并判断类型 =========
        const content = await app.vault.read(archiveFile);
        const isClass = content.includes("#班课档案");
        const isOneOnOne = content.includes("#一对一");

        if (!isClass && !isOneOnOne) throw new Error("无法识别档案类型（缺少 #班课档案 或 #一对一 标签）");

        // ========= 4. 提取学员名单（班课） =========
        let students = [];
        if (isClass) {
            const lines = content.split("\n");
            let inTable = false;
            let tableFound = false;

            for (const line of lines) {
                if (line.includes("## 👥 学员名单")) {
                    inTable = true;
                    continue;
                }
                if (inTable && !tableFound) {
                    if (line.startsWith("|") && line.includes("---")) {
                        tableFound = true;
                        continue;
                    }
                }
                if (inTable && tableFound && line.startsWith("|")) {
                    const parts = line.split("|").map(p => p.trim());
                    if (parts.length > 2) {
                        const name = parts[1];
                        if (name && name !== "姓名") {
                            students.push(name);
                        }
                    }
                    continue;
                }
                if (inTable && tableFound && line.trim() === "") {
                    break;
                }
            }

            if (students.length === 0) throw new Error("未找到学员名单");
        } else {
            students = [targetName];
        }

        // ========= 5. 创建测试反馈文件夹和文件 =========
        const testFolderPath = `${targetFolder.path}/${testName}`;
        let testFolder = app.vault.getAbstractFileByPath(testFolderPath);
        if (!testFolder) {
            await app.vault.createFolder(testFolderPath);
        }

        const testFilePath = `${testFolderPath}/${testName}.md`;
        let existingTestFile = app.vault.getAbstractFileByPath(testFilePath);

        // 生成学生区块
        const studentBlocks = students.map(s =>
            `### ${s}\n- [ ] 参加结班测\n- [ ] 反馈已写完`
        ).join("\n\n");

        const testContent = `---
tags: ["#测试反馈"]
test_name: "${testName}"
test_date: "${testDate}"
student_count: ${students.length}
---

## 📋 ${testName}总览

${studentBlocks}
`;

        if (existingTestFile) {
            await app.vault.modify(existingTestFile, testContent);
            new Notice(`⚠️ 已更新测试文件：${testFilePath}`);
        } else {
            await app.vault.create(testFilePath, testContent);
            new Notice(`📁 已创建测试文件：${testFilePath}`);
        }

        // ========= 6. 在档案首页追加链接 =========
        const linkLine = `- [[${testName}/${testName}|📝 ${testName}]]`;
        let updatedContent = content;

        if (!content.includes("## 📋 测试反馈")) {
            updatedContent += `\n\n## 📋 测试反馈\n${linkLine}\n`;
        } else {
            const parts = content.split("## 📋 测试反馈");
            updatedContent = parts[0] + "## 📋 测试反馈\n" + parts[1].trimEnd() + "\n" + linkLine;
        }

        await app.vault.modify(archiveFile, updatedContent);
        new Notice(`🔗 已更新档案链接`);

        // ========= 7. 打开测试文件 =========
        const newTestFile = app.vault.getAbstractFileByPath(testFilePath);
        if (newTestFile) {
            await app.workspace.getLeaf(true).openFile(newTestFile);
        }

        new Notice(`✅ ${targetName} 的「${testName}」创建完成！`);

    } catch (error) {
        new Notice(`❌ 运行失败：${error.message}`, 6000);
        console.error("QuickAdd 脚本错误:", error);
    }
};
