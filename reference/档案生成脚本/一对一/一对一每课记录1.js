module.exports = async () => {

    try {

        // ========= 1. 选择学员档案文件夹 =========

        const allFiles = app.vault.getAllLoadedFiles();
        const allFolders = allFiles.filter(f => f.children).map(f => f.path).filter(p => p !== "").sort();
        
        const candidateFolders = allFolders;

        const selectedFolder = await app.plugins.plugins.quickadd.api.suggester(
            candidateFolders,
            candidateFolders,
            false,
            "请选择学员档案文件夹 (包含 {学员名}.md 的文件夹)"
        );

        if (!selectedFolder) throw new Error("未选择文件夹");

        // ========= 2. 解析学员信息与档案页 =========

        const folderName = selectedFolder.split('/').pop();
        
        let archiveFileName = `${folderName}.md`;
        let archiveFilePath = `${selectedFolder}/${archiveFileName}`;
        let archiveFile = app.vault.getAbstractFileByPath(archiveFilePath);

        if (!archiveFile) {
            const mdFilesInFolder = allFiles
                .filter(f => f.path.startsWith(selectedFolder + '/') && f.name.endsWith('.md'))
                .map(f => f.path);
            
            if (mdFilesInFolder.length === 1) {
                archiveFilePath = mdFilesInFolder[0];
                archiveFile = app.vault.getAbstractFileByPath(archiveFilePath);
                archiveFileName = archiveFile.name;
            } else if (mdFilesInFolder.length > 1) {
                archiveFilePath = await app.plugins.plugins.quickadd.api.suggester(
                    mdFilesInFolder,
                    mdFilesInFolder,
                    false,
                    "检测到多个 Markdown 文件，请选择档案首页"
                );
                if (!archiveFilePath) throw new Error("未选择档案页");
                archiveFile = app.vault.getAbstractFileByPath(archiveFilePath);
                archiveFileName = archiveFile.name;
            } else {
                throw new Error(`在 "${selectedFolder}" 中未找到有效的档案页 (.md 文件)`);
            }
        }

        const content = await app.vault.read(archiveFile);
        
        const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
        if (!frontmatterMatch) throw new Error("档案页缺少 Frontmatter (--- 包裹的部分)");
        
        const frontmatterStr = frontmatterMatch[1];
        const parseYamlLine = (line) => {
            const [key, ...valParts] = line.split(':');
            if (!key || valParts.length === 0) return null;
            const value = valParts.join(':').trim().replace(/^["']|["']$/g, '');
            return { key: key.trim(), value };
        };

        const frontmatterLines = frontmatterStr.split('\n');
        const meta = {};
        const tagsList = [];
        
        let inTagsBlock = false;
        
        for (const line of frontmatterLines) {
            if (inTagsBlock) {
                if (line.trim().startsWith('- ')) {
                    const tagValue = line.trim().substring(2).replace(/^["']|["']$/g, '');
                    tagsList.push(tagValue);
                    continue;
                } else {
                    inTagsBlock = false;
                }
            }
            
            if (!line.trim()) continue;
            
            const parsed = parseYamlLine(line);
            if (parsed) {
                if (parsed.key === 'tags') {
                    const arrMatch = parsed.value.match(/\[(.*)\]/);
                    if (arrMatch) {
                        tagsList.push(...arrMatch[1].split(',').map(s => s.trim().replace(/^["']|["']$/g, '')));
                    } else {
                        inTagsBlock = true;
                    }
                } else {
                    meta[parsed.key] = parsed.value;
                }
            } else if (line.trim() === 'tags:') {
                inTagsBlock = true;
            }
        }

        const studentName = folderName;
        const currentTotal = parseInt(meta['total_lessons'] || '0');

        const curriculumTags = tagsList
            .filter(tag => !['#学员档案', '#一对一'].includes(tag))
            .map(tag => tag.replace(/^#/, ''));

        // ========= 3. 自动推算课次 =========

        const lessonFolderPattern = /Lesson\s*(\d+)/i;
        let maxLessonNum = 0;

        const subFolders = allFiles
            .filter(f => f.children && f.path.startsWith(selectedFolder + '/'))
            .map(f => f.path);

        for (const path of subFolders) {
            const match = path.match(lessonFolderPattern);
            if (match) {
                const num = parseInt(match[1]);
                if (num > maxLessonNum) maxLessonNum = num;
            }
        }

        const nextLessonNum = maxLessonNum + 1;

        // ========= 4. 选择课程体系 (Tag) =========

        let selectedTag;
        let isNewTag = false;
        
        const courseOptions = [
            "Foundation Grammar",
            "L1教材",
            "L1讲义",
            "L2教材",
            "L2讲义",
            "精讲精练"
        ];
        
        const defaultTag = curriculumTags.length > 0 ? curriculumTags[curriculumTags.length - 1] : null;
        
        if (!defaultTag) {
            selectedTag = await app.plugins.plugins.quickadd.api.suggester(
                courseOptions,
                courseOptions,
                false,
                "请选择课程体系"
            );
            if (!selectedTag) throw new Error("未选择课程体系");
            isNewTag = true;
        } else {
            const otherOptions = courseOptions.filter(opt => opt !== defaultTag);
            const tagOptions = [`默认 (${defaultTag})`, ...otherOptions];
            
            selectedTag = await app.plugins.plugins.quickadd.api.suggester(
                tagOptions,
                tagOptions,
                false,
                `请选择本节课所属的课程体系`
            );
            if (!selectedTag) throw new Error("未选择课程体系");
            
            if (selectedTag === `默认 (${defaultTag})`) {
                selectedTag = defaultTag;
            } else {
                isNewTag = true;
            }
        }

        // ========= 5. 计算时间 =========

        function getNearestTimeToday() {
            const now = new Date();
            const timeOptions = [
                { h: 10, m: 0 },
                { h: 12, m: 20 },
                { h: 15, m: 30 },
                { h: 17, m: 50 },
                { h: 20, m: 10 }
            ];
            let nearest = null;
            let minDiff = Infinity;
            for (const t of timeOptions) {
                const candidate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), t.h, t.m, 0);
                const diff = Math.abs(now - candidate);
                if (diff < minDiff) {
                    minDiff = diff;
                    nearest = candidate;
                }
            }
            return nearest;
        }

        function formatISO(date) {
            const pad = n => n.toString().padStart(2, "0");
            const year = date.getFullYear();
            const month = pad(date.getMonth() + 1);
            const day = pad(date.getDate());
            const hours = pad(date.getHours());
            const minutes = pad(date.getMinutes());
            const seconds = pad(date.getSeconds());
            const offsetMinutes = -date.getTimezoneOffset();
            const sign = offsetMinutes >= 0 ? "+" : "-";
            const offsetH = pad(Math.floor(Math.abs(offsetMinutes) / 60));
            const offsetM = pad(Math.abs(offsetMinutes) % 60);
            return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${sign}${offsetH}:${offsetM}`;
        }

        const timeModeOptions = ["🤖 自动识别（推荐）", "📅 手动选择"];
        const timeMode = await app.plugins.plugins.quickadd.api.suggester(
            timeModeOptions,
            timeModeOptions,
            false,
            "请选择课程时间获取方式"
        );

        let lessonDate, isoDate, dateStr;
        if (!timeMode || timeMode === "🤖 自动识别（推荐）") {
            lessonDate = getNearestTimeToday();
            isoDate = formatISO(lessonDate);
            dateStr = lessonDate.toISOString().split('T')[0];
        } else {
            const manualDate = await app.plugins.plugins.quickadd.api.datePrompt(
                "请选择课程日期",
                "YYYY-MM-DD"
            );
            if (!manualDate) throw new Error("未选择日期");

            const timeOptions = ["10:00", "12:20", "15:30", "17:50", "20:10"];
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
            const offsetH = pad(Math.floor(Math.abs(offset) / 60));
            const offsetM = pad(Math.abs(offset) % 60);

            isoDate = `${year}-${month}-${day}T${hours}:${minutes}:00${sign}${offsetH}:${offsetM}`;
            dateStr = `${year}-${month}-${day}`;
            lessonDate = manualDateTime;
        }

        // 格式化作业日期（如 6月21日）
        const [, month, day] = dateStr.split('-');
        const monthDay = `${parseInt(month)}月${parseInt(day)}日`;

        // ========= 6. 构建路径与文件 =========

        const lessonFolderName = `${studentName} Lesson ${nextLessonNum}`;
        const lessonFolderPath = `${selectedFolder}/${lessonFolderName}`;
        
        let lessonFolder = app.vault.getAbstractFileByPath(lessonFolderPath);
        if (!lessonFolder) {
            await app.vault.createFolder(lessonFolderPath);
        } else {
            if (!confirm(`课程文件夹 "${lessonFolderPath}" 已存在，是否覆盖内部文件？`)) {
                throw new Error("用户取消操作");
            }
        }

        const filesToCreate = [
            { name: `${studentName} Lesson ${nextLessonNum}.md`, type: 'nav' },
            { name: `Note ${nextLessonNum}.md`, type: 'empty' },
            { name: `Wordlist ${nextLessonNum}.md`, type: 'empty' },
            { name: `Grammar Note ${nextLessonNum}.md`, type: 'empty' },
            { name: `Homework ${nextLessonNum}.md`, type: 'empty' },
            { name: `Quiz ${nextLessonNum + 1}.md`, type: 'empty' },
            { name: `Feedback ${nextLessonNum}.md`, type: 'feedback' }
        ];

        // ========= 7. 生成文件内容 =========

        for (const fileDef of filesToCreate) {
            const filePath = `${lessonFolderPath}/${fileDef.name}`;
            let content = "";

            if (fileDef.type === 'nav') {
                content = `---
Date: ${isoDate}
tags:
  - "#课程记录"
  - "#${selectedTag}"
need_send_feedback: true
archive: "[[${studentName}|📁 档案首页]]"
---
## 📂本节课文件
- [[Note ${nextLessonNum}|📝 课堂笔记]]
- [[Wordlist ${nextLessonNum}|📚 词汇表]]
- [[Grammar Note ${nextLessonNum}|📖 语法笔记]]
- [[Homework ${nextLessonNum}|✍️ 课后作业]]
- [[Quiz ${nextLessonNum + 1}|📋 下节课入门测]]
---
## 📝 学员反馈
- [ ] 提交反馈
- [[Feedback ${nextLessonNum}|💬 课堂反馈]]
---
### 授课内容

## ✍️作业记录
- [ ] 发送作业到家长群
${monthDay}阅读作业：

---
## 📌 下次课提醒

- [ ] 准备打印作业
- [ ] 准备入门测

`;
            } else if (fileDef.type === 'feedback') {
                content = `## 👤 ${studentName}


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
`;
            } else {
                content = "";
            }

            const existing = app.vault.getAbstractFileByPath(filePath);
            if (existing) {
                await app.vault.modify(existing, content);
            } else {
                await app.vault.create(filePath, content);
            }
        }

        // ========= 8. 更新档案页 (回填索引) =========

        const newLink = `- [[${lessonFolderName}|第 ${nextLessonNum} 课 - ${dateStr}]]`;
        
        let currentContent = await app.vault.read(archiveFile);
        
        if (isNewTag) {
            const newTagLine = `  - "#${selectedTag}"`;
            
            const lines = currentContent.split('\n');
            let lastTagIndex = -1;
            let inTagsSection = false;
            
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].trim() === 'tags:') {
                    inTagsSection = true;
                    continue;
                }
                if (inTagsSection) {
                    if (lines[i].trim().startsWith('- ')) {
                        lastTagIndex = i;
                    } else if (lines[i].trim() === '---' || (lines[i].trim() && !lines[i].trim().startsWith('-'))) {
                        break;
                    }
                }
            }
            
            if (lastTagIndex !== -1) {
                lines.splice(lastTagIndex + 1, 0, newTagLine);
                currentContent = lines.join('\n');
            }
            
            const 课程索引位置 = currentContent.indexOf("## 📚 课程索引");
            if (课程索引位置 !== -1) {
                const sectionEndMarker = currentContent.indexOf("## 📈 成长轨迹", 课程索引位置);
                const sectionEnd = sectionEndMarker !== -1 ? sectionEndMarker : currentContent.length;
                const sectionContent = currentContent.substring(课程索引位置, sectionEnd);
                
                const lastDividerInSection = sectionContent.lastIndexOf("---");
                if (lastDividerInSection !== -1) {
                    const insertPosition = 课程索引位置 + lastDividerInSection + 3;
                    const newBlock = `\n\n### 🏷️ ${selectedTag}\n${newLink}\n\n---\n`;
                    currentContent = currentContent.substring(0, insertPosition) + newBlock + currentContent.substring(insertPosition);
                }
            }
            
            const updatedTotal = nextLessonNum;
            currentContent = currentContent
                .replace(/(total_lessons:\s*)(\d+)/, `$1${updatedTotal}`)
                .replace(/(last_lesson_date:\s*)(null|.*)/, `$1"${dateStr}"`);
            
            await app.vault.modify(archiveFile, currentContent);
            new Notice(`✅ 档案页索引已更新 (总课次：${updatedTotal})`);
        } else {
            const targetHeader = `### 🏷️ ${selectedTag}`;
            const headerPosition = currentContent.indexOf(targetHeader);
            
            if (headerPosition !== -1) {
                const afterHeader = currentContent.substring(headerPosition);
                const firstDivider = afterHeader.indexOf("\n---");
                
                if (firstDivider !== -1) {
                    const insertPosition = headerPosition + firstDivider;
                    currentContent = currentContent.substring(0, insertPosition) + '\n' + newLink + currentContent.substring(insertPosition);
                }
            }
        }
        
        const updatedTotal = nextLessonNum;
        currentContent = currentContent
            .replace(/(total_lessons:\s*)(\d+)/, `$1${updatedTotal}`)
            .replace(/(last_lesson_date:\s*)(null|.*)/, `$1"${dateStr}"`);
        
        await app.vault.modify(archiveFile, currentContent);
        new Notice(`✅ 档案页索引已更新 (总课次：${updatedTotal})`);

        // ========= 9. 打开导航页 =========

        const navFilePath = `${lessonFolderPath}/${studentName} Lesson ${nextLessonNum}.md`;
        const navFile = app.vault.getAbstractFileByPath(navFilePath);
        if (navFile) {
            await app.workspace.getLeaf().openFile(navFile);
            new Notice(`✅ 第 ${nextLessonNum} 课记录包生成成功！`);
        }

    } catch (err) {
        console.error("One-on-One Lesson Record Error:", err);
        new Notice(`❌ 生成失败：${err.message}`);
    }
};
