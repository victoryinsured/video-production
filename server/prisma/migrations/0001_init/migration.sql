-- CreateTable
CREATE TABLE "BrandTemplate" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "colors" TEXT NOT NULL,
    "fonts" TEXT NOT NULL,
    "cover" TEXT NOT NULL,
    "logoPath" TEXT,
    "introVideoPath" TEXT,
    "outroVideoPath" TEXT,
    "width" INTEGER NOT NULL DEFAULT 1920,
    "height" INTEGER NOT NULL DEFAULT 1080,
    "fps" INTEGER NOT NULL DEFAULT 30,
    "audioBitrate" TEXT NOT NULL DEFAULT '192k',
    "captionsEnabled" BOOLEAN NOT NULL DEFAULT false,
    "captionFontSize" INTEGER NOT NULL DEFAULT 34,
    "captionPosition" TEXT NOT NULL DEFAULT 'bottom',
    "textScale" REAL NOT NULL DEFAULT 1.0,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Voice" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "elevenLabsVoiceId" TEXT NOT NULL,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Course" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "title" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "status" TEXT NOT NULL DEFAULT 'draft',
    "brandTemplateId" TEXT,
    "voiceId" TEXT,
    "awsBucket" TEXT,
    "awsRegion" TEXT,
    "awsKeyPrefix" TEXT,
    "bunnyLibraryId" TEXT,
    "bunnyCollectionId" TEXT,
    "moodleCourseId" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Course_brandTemplateId_fkey" FOREIGN KEY ("brandTemplateId") REFERENCES "BrandTemplate" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Course_voiceId_fkey" FOREIGN KEY ("voiceId") REFERENCES "Voice" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Module" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "courseId" TEXT NOT NULL,
    "number" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "order" INTEGER NOT NULL DEFAULT 0,
    "moodleSectionId" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Module_courseId_fkey" FOREIGN KEY ("courseId") REFERENCES "Course" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Lesson" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "moduleId" TEXT NOT NULL,
    "number" TEXT NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0,
    "title" TEXT NOT NULL,
    "lessonType" TEXT NOT NULL DEFAULT 'video',
    "description" TEXT NOT NULL DEFAULT '',
    "videoDescription" TEXT NOT NULL DEFAULT '',
    "scriptText" TEXT NOT NULL DEFAULT '',
    "scriptHash" TEXT NOT NULL DEFAULT '',
    "knowledgeChecks" TEXT NOT NULL DEFAULT '[]',
    "productionInstructions" TEXT NOT NULL DEFAULT '',
    "tags" TEXT NOT NULL DEFAULT '[]',
    "brandTemplateId" TEXT,
    "voiceId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'not_started',
    "videoPath" TEXT,
    "videoDurationSeconds" REAL,
    "narrationPath" TEXT,
    "editableAssetPath" TEXT,
    "bunnyVideoId" TEXT,
    "awsVideoKey" TEXT,
    "moodleActivityId" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Lesson_moduleId_fkey" FOREIGN KEY ("moduleId") REFERENCES "Module" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Resource" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "lessonId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "instructions" TEXT NOT NULL DEFAULT '',
    "filename" TEXT NOT NULL DEFAULT '',
    "resourceType" TEXT NOT NULL DEFAULT 'file',
    "storagePath" TEXT,
    "linkUrl" TEXT,
    "awsKey" TEXT,
    "moodleFileId" INTEGER,
    "moodleActivityId" INTEGER,
    "status" TEXT NOT NULL DEFAULT 'not_started',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Resource_lessonId_fkey" FOREIGN KEY ("lessonId") REFERENCES "Lesson" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Document" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "courseId" TEXT,
    "filename" TEXT NOT NULL,
    "storedPath" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'uploaded',
    "parsedCourseJson" TEXT,
    "diffJson" TEXT,
    "error" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Document_courseId_fkey" FOREIGN KEY ("courseId") REFERENCES "Course" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "JobStep" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "lessonId" TEXT NOT NULL,
    "resourceId" TEXT NOT NULL DEFAULT '',
    "step" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "error" TEXT,
    "resultJson" TEXT,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "JobStep_lessonId_fkey" FOREIGN KEY ("lessonId") REFERENCES "Lesson" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AdminUser" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "Course_slug_key" ON "Course"("slug");

-- CreateIndex
CREATE INDEX "Course_status_idx" ON "Course"("status");

-- CreateIndex
CREATE INDEX "Module_courseId_idx" ON "Module"("courseId");

-- CreateIndex
CREATE UNIQUE INDEX "Module_courseId_number_key" ON "Module"("courseId", "number");

-- CreateIndex
CREATE INDEX "Lesson_moduleId_idx" ON "Lesson"("moduleId");

-- CreateIndex
CREATE UNIQUE INDEX "Lesson_moduleId_number_key" ON "Lesson"("moduleId", "number");

-- CreateIndex
CREATE INDEX "Resource_lessonId_idx" ON "Resource"("lessonId");

-- CreateIndex
CREATE INDEX "Document_courseId_idx" ON "Document"("courseId");

-- CreateIndex
CREATE INDEX "JobStep_status_idx" ON "JobStep"("status");

-- CreateIndex
CREATE INDEX "JobStep_lessonId_idx" ON "JobStep"("lessonId");

-- CreateIndex
CREATE UNIQUE INDEX "JobStep_lessonId_step_resourceId_key" ON "JobStep"("lessonId", "step", "resourceId");

-- CreateIndex
CREATE UNIQUE INDEX "AdminUser_email_key" ON "AdminUser"("email");

