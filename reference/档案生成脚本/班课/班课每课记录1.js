module.exports = async () => {
    try {

        // ========= 获取学生 =========
        async function getStudentsFromArchive(classFolder, className) {

            const archivePath = `${classFolder}/${className}.md`;
            const archiveFile = app.vault.getAbstractFileByPath(archivePath);

            let students = [];

            if (!archiveFile) return students;

            const content = await app.vault.read(archiveFile);
            const lines = content.split('\n');

            let tableStart = false;

            for (let line of lines) {

                if (line.includes("姓名")) {
                    tableStart = true;
                    continue;
                }

                if (tableStart) {

                    if (!line.startsWith("|")) break;

                    if (line.includes("---")) continue;

                    const parts = line.split("|").map(x => x.trim());
                    const name = parts[1];

                    if (name && name !== "姓名") {
                        students.push({ name: name });
                    }
                }
            }

            return students;
        }


        // ========= 自动读取课次 =========
        async function getNextLessonNumber(classFolder, className) {

            const archivePath = `${classFolder}/${className}.md`;
            const archiveFile = app.vault.getAbstractFileByPath(archivePath);

            if (!archiveFile) return 1;

            const content = await app.vault.read(archiveFile);

            const matches = [...content.matchAll(/Lesson (\d+)/g)];

            if (matches.length === 0) return 1;

            const numbers = matches.map(m => parseInt(m[1]));
            const max = Math.max(...numbers);

            return max + 1;
        }


        // ========= 获取最近课程时间 =========
        function getCurrentTimeISO() {

            const now = new Date();

            const times = [
                { h: 10, m: 0 },
                { h: 12, m: 20 },
                { h: 15, m: 30 },
                { h: 17, m: 50 }
            ];

            let closestTime = null;
            let smallestDiff = Infinity;

            for (const t of times) {

                const lessonTime = new Date(now);

                lessonTime.setHours(t.h);
                lessonTime.setMinutes(t.m);
                lessonTime.setSeconds(0);

                const diff = Math.abs(now - lessonTime);

                if (diff < smallestDiff) {
                    smallestDiff = diff;
                    closestTime = lessonTime;
                }
            }

            const pad = n => n.toString().padStart(2, "0");

            const year = closestTime.getFullYear();
            const month = pad(closestTime.getMonth() + 1);
            const day = pad(closestTime.getDate());

            const hours = pad(closestTime.getHours());
            const minutes = pad(closestTime.getMinutes());
            const seconds = "00";

            const offset = -closestTime.getTimezoneOffset();
            const sign = offset >= 0 ? "+" : "-";

            const offsetHours = pad(Math.floor(Math.abs(offset) / 60));
            const offsetMinutes = pad(Math.abs(offset) % 60);

            return {
                iso: `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${sign}${offsetHours}:${offsetMinutes}`,
                dateStr: `${year}-${month}-${day}`
            };
        }

        // 让用户选择时间获取方式
        const timeModeOptions = ["🤖 自动识别（推荐）", "📅 手动选择"];
        const timeMode = await app.plugins.plugins.quickadd.api.suggester(
            timeModeOptions,
            timeModeOptions,
            false,
            "请选择课程时间获取方式"
        );

        let timeInfo;
        if (!timeMode || timeMode === "🤖 自动识别（推荐）") {
            timeInfo = getCurrentTimeISO();
        } else {
            const manualDate = await app.plugins.plugins.quickadd.api.datePrompt(
                "请选择课程日期",
                "YYYY-MM-DD"
            );
            if (!manualDate) throw new Error("未选择日期");

            const timeOptions = ["10:00", "12:20", "15:30", "17:50"];
            const manualTime = await app.plugins.plugins.quickadd.api.suggester(
                timeOptions,
                timeOptions,
                false,
                "请选择课程时间"
            );
            if (!manualTime) throw new Error("未选择时间");

            const [hours, minutes] = manualTime.split(':');
            const manualDateTime = new Date(manualDate + 'T' + manualTime + ':00');
            
            const pad = n => n.toString().padStart(2, "0");
            const year = manualDateTime.getFullYear();
            const month = pad(manualDateTime.getMonth() + 1);
            const day = pad(manualDateTime.getDate());
            const offset = -manualDateTime.getTimezoneOffset();
            const sign = offset >= 0 ? "+" : "-";
            const offsetHours = pad(Math.floor(Math.abs(offset) / 60));
            const offsetMinutes = pad(Math.abs(offset) % 60);

            timeInfo = {
                iso: `${year}-${month}-${day}T${hours}:${minutes}:00${sign}${offsetHours}:${offsetMinutes}`,
                dateStr: `${year}-${month}-${day}`
            };
        }


        // ========= 获取班级 =========
        const allFolders = app.vault.getAllLoadedFiles()
            .filter(f => f.children)
            .map(f => f.path)
            .filter(p => p !== "")
            .sort();

        const classFolders = allFolders.filter(f =>
            f.includes("班") ||
            f.includes("Class") ||
            f.includes("class")
        );

        if (classFolders.length === 0) {
            throw new Error("未找到班级文件夹");
        }

        const selectedClassFolder = await app.plugins.plugins.quickadd.api.suggester(
            classFolders,
            classFolders,
            false,
            "请选择班级"
        );

        if (!selectedClassFolder) throw new Error("未选择班级");

        const className = selectedClassFolder.split("/").pop();


        // ========= 自动课次 =========
        const lessonNumber = await getNextLessonNumber(selectedClassFolder, className);
        const nextLesson = lessonNumber + 1;


        // ========= 学生 =========
        const students = await getStudentsFromArchive(selectedClassFolder, className);


        // ========= 读取课程体系标签 =========
        async function getCourseType(classFolder, className) {
            const archivePath = `${classFolder}/${className}.md`;
            const archiveFile = app.vault.getAbstractFileByPath(archivePath);
            if (!archiveFile) return "班课";

            const content = await app.vault.read(archiveFile);
            const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
            if (!frontmatterMatch) return "班课";

            const frontmatterStr = frontmatterMatch[1];
            const tagsMatch = frontmatterStr.match(/tags:\s*\[([^\]]+)\]/);
            if (!tagsMatch) return "班课";

            const tagsStr = tagsMatch[1];
            const tags = tagsStr.split(',').map(t => t.trim().replace(/^["']|["']$/g, ''));
            
            // 过滤掉固定标签，取最后一个课型标签
            const courseTags = tags.filter(t => !['#班课档案'].includes(t));
            return courseTags.length > 0 ? courseTags[courseTags.length - 1].replace('#', '') : "班课";
        }

        const courseType = await getCourseType(selectedClassFolder, className);


        // ========= 读取班型（schedule_type）=========
        async function getScheduleType(classFolder, className) {
            const archivePath = `${classFolder}/${className}.md`;
            const archiveFile = app.vault.getAbstractFileByPath(archivePath);
            if (!archiveFile) return "full-time";

            const content = await app.vault.read(archiveFile);
            const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
            if (!frontmatterMatch) return "full-time";

            const frontmatterStr = frontmatterMatch[1];
            const scheduleMatch = frontmatterStr.match(/schedule_type:\s*["']?(\w+)["']?/);
            return scheduleMatch ? scheduleMatch[1] : "full-time";
        }

        const scheduleType = await getScheduleType(selectedClassFolder, className);
        const needSendFeedback = scheduleType === 'weekend' || lessonNumber % 2 === 0;


        // ========= 时间 =========
        const dateISO = timeInfo.iso;
        const dateStr = timeInfo.dateStr;

        // 格式化作业日期（如 6月21日）
        const [, month, day] = dateStr.split('-');
        const monthDay = `${parseInt(month)}月${parseInt(day)}日`;


        // ========= 文件夹 =========
        const lessonFolderName = `${className} Lesson ${lessonNumber}`;
        const lessonFolderPath = `${selectedClassFolder}/${lessonFolderName}`;

        let lessonFolder = app.vault.getAbstractFileByPath(lessonFolderPath);

        if (!lessonFolder) {

            await app.vault.createFolder(lessonFolderPath);

            new Notice(`📁 创建课程文件夹 ${lessonFolderName}`);
        }


        // ========= 课程导航 =========
        function generateNav() {

            return `---
Date: ${dateISO}
tags:
  - "#课程记录"
  - "#${courseType}"
need_send_feedback: ${needSendFeedback}
archive: "[[${className}|📁 档案首页]]"
---
## 📂本节课文件
- [[Note ${lessonNumber}|📝 课堂笔记]]
- [[Wordlist ${lessonNumber}|📚 词表]]
- [[Grammar Note ${lessonNumber}|📖 语法笔记]]
- [[Homework ${lessonNumber}|✍️ 课后作业]]
- [[Quiz ${nextLesson}|📋 下节课入门测]]
- [[Feedback ${lessonNumber}|💬 学员反馈]]
---
## 📝 班级反馈
- [ ] 提交反馈
- [[Feedback ${lessonNumber}|💬 学员反馈]]

### 授课内容



### 原始记录

#### 出勤



#### 整体表现



#### 作业情况



#### 入门测情况



#### 授课进度


### 反馈总结
<!-- AI_GENERATED_START -->
待生成
<!-- AI_GENERATED_END -->

---

## ✍️作业记录
- [ ] 发送作业到家长群
${monthDay}阅读作业：


---
## 📌 下次课提醒

- [ ] 准备打印作业
- [ ] 准备入门测

`;
        }


        // ========= 反馈文件 =========
        function generateFeedback() {

            const sections = students.map(s =>

`## 👤 ${s.name}

### 原始记录

#### 出勤


#### 作业情况


#### 入门测情况


#### 课堂表现


#### 掌握情况


#### 需要加强


### 反馈总结
<!-- AI_GENERATED_START -->
待生成

<!-- AI_GENERATED_END -->

`).join("\n");

            return `${sections}`;
        }


        // ========= 文件 =========
        const files = [

            { name: `${className} Lesson ${lessonNumber}`, content: generateNav() },
            { name: `Note ${lessonNumber}`, content: "" },
            { name: `Wordlist ${lessonNumber}`, content: "" },
            { name: `Grammar Note ${lessonNumber}`, content: "" },
            { name: `Homework ${lessonNumber}`, content: "" },
            { name: `Quiz ${nextLesson}`, content: "" },
            { name: `Feedback ${lessonNumber}`, content: generateFeedback() }

        ];


        for (const f of files) {

            const path = `${lessonFolderPath}/${f.name}.md`;
            const exists = app.vault.getAbstractFileByPath(path);

            if (!exists) {

                await app.vault.create(path, f.content);
                new Notice(`📄 创建 ${f.name}`);
            }
        }


        // ========= 更新班级档案 =========
        async function updateArchive() {

            const archivePath = `${selectedClassFolder}/${className}.md`;
            const archiveFile = app.vault.getAbstractFileByPath(archivePath);

            if (!archiveFile) return;

            let content = await app.vault.read(archiveFile);

            const lessonLink = `- [[${lessonFolderName}|📖 Lesson ${lessonNumber} - ${dateStr}]]`;

            if (!content.includes(lessonLink)) {
                const indexHeader = "## 📅 课程记录索引";
                const headerPos = content.indexOf(indexHeader);
                if (headerPos !== -1) {
                    const afterHeader = content.substring(headerPos);
                    const dividerPos = afterHeader.indexOf("\n---");
                    if (dividerPos !== -1) {
                        const insertPos = headerPos + dividerPos;
                        content = content.substring(0, insertPos) + '\n' + lessonLink + content.substring(insertPos);
                    }
                }

                // 更新 total_lessons 和 last_lesson_date
                const updatedTotal = lessonNumber;
                content = content
                    .replace(/(total_lessons:\s*)(\d+)/, `$1${updatedTotal}`)
                    .replace(/(last_lesson_date:\s*)(null|.*)/, `$1"${dateStr}"`);

                await app.vault.modify(archiveFile, content);
            }
        }

        await updateArchive();


        // ========= 打开导航 =========
        const navPath = `${lessonFolderPath}/${className} Lesson ${lessonNumber}.md`;
        const navFile = app.vault.getAbstractFileByPath(navPath);

        if (navFile) {
            await app.workspace.getLeaf(true).openFile(navFile);
        }

        new Notice(`✅ Lesson ${lessonNumber} 创建完成`);

    } catch (error) {

        new Notice(`❌ ${error.message}`, 6000);
        console.error(error);
    }
};