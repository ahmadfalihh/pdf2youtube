const { OpenAI } = require('openai');
const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');

const FOLDER_ANTREAN_ID = process.env.FOLDER_ANTREAN_ID;
const FOLDER_SELESAI_ID = process.env.FOLDER_SELESAI_ID;
const MAX_UPLOAD_PER_DAY = 20;

const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET
);
oauth2Client.setCredentials({ refresh_token: process.env.GOOGLE_REFRESH_TOKEN });

const drive = google.drive({ version: 'v3', auth: oauth2Client });
const youtube = google.youtube({ version: 'v3', auth: oauth2Client });

const TEMP_DIR = path.join(__dirname, 'temp_yt');

async function main() {
  console.log('🤖 YT-Auto-Uploader Bangun dari Tidur...');
  if (!fs.existsSync(TEMP_DIR)) fs.mkdirSync(TEMP_DIR);

  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const uploadedToday = await drive.files.list({
      q: `'${FOLDER_SELESAI_ID}' in parents and modifiedTime > '${today.toISOString()}'`,
      fields: 'files(id)'
    });

    if (uploadedToday.data.files.length >= MAX_UPLOAD_PER_DAY) {
      console.log(`🛑 Kuota harian (${MAX_UPLOAD_PER_DAY}) sudah tercapai. Mesin kembali tidur sampai besok.`);
      return;
    }

    const antrean = await drive.files.list({
      q: `'${FOLDER_ANTREAN_ID}' in parents and mimeType contains 'video/'`,
      orderBy: 'createdTime asc', 
      pageSize: 1,
      fields: 'files(id, name, mimeType)'
    });

    if (antrean.data.files.length === 0) {
      console.log('📭 Tidak ada video baru di Folder Antrean. Mesin kembali tidur.');
      return;
    }

    const videoInfo = antrean.data.files[0];
    console.log(`🎥 Ditemukan video: "${videoInfo.name}".`);

    const delayMenit = Math.floor(Math.random() * 45) + 1;
    console.log(`⏳ [ANTI-SPAM] Mesin akan menunggu secara acak selama ${delayMenit} menit sebelum memproses...`);
    await new Promise(resolve => setTimeout(resolve, delayMenit * 60 * 1000));
    console.log('🚀 Waktu jeda selesai! Mulai mengeksekusi...');

    console.log('🧠 Meracik SEO Super Viral dengan KoboiLLM...');
    const seoData = await generateViralSEO(videoInfo.name);
    
    console.log('📥 Mengunduh video mentah ke server GitHub...');
    const videoPath = path.join(TEMP_DIR, 'upload_target.mp4');
    await downloadFile(videoInfo.id, videoPath);

    console.log(`▶️ Mengunggah ke YouTube: "${seoData.title}"...`);
    const ytVideoId = await uploadToYouTube(videoPath, seoData);
    
    console.log('📦 Memindahkan video asli ke folder Selesai di Drive...');
    await drive.files.update({
      fileId: videoInfo.id,
      addParents: FOLDER_SELESAI_ID,
      removeParents: FOLDER_ANTREAN_ID,
      fields: 'id, parents'
    });

    console.log(`✅ TUNTAS! Link: https://youtu.be/${ytVideoId}`);

  } catch (error) {
    console.error('❌ TERJADI KESALAHAN:', error);
  }
}

async function downloadFile(fileId, destPath) {
  const dest = fs.createWriteStream(destPath);
  const res = await drive.files.get({ fileId: fileId, alt: 'media' }, { responseType: 'stream' });
  return new Promise((resolve, reject) => res.data.pipe(dest).on('finish', resolve).on('error', reject));
}

async function generateViralSEO(filename) {
  const openai = new OpenAI({
    apiKey: process.env.KOBOI_API_KEY,
    baseURL: "https://litellm.koboi2026.biz.id/v1"
  });

  const prompt = `Anda adalah pakar YouTube Growth Hacker & SEO Specialist tingkat dunia. \nSaya punya video dengan nama file mentah: "${filename}". \nTugas Anda adalah meracik metadata yang memaksa orang mengklik (Clickbait yang jujur) dan sangat mudah meranking di pencarian YouTube (SEO High Engagement).\n\nATURAN WAJIB:\n1. Judul: Bikin penasaran, dramatis, SEO friendly (Maks. 70 karakter).\n2. Deskripsi: Tulis 300 kata yang persuasif, berikan nilai/manfaat jika menonton, sertakan call-to-action (Like/Subscribe). Tambahkan 5 hashtag (#) yang paling trending.\n3. Tags: Berikan 15 kata kunci pencarian yang volume-nya tinggi, pisahkan dengan koma.\n\nKEMBALIKAN HANYA DALAM FORMAT JSON TANPA TEKS LAIN/MARKDOWN:\n{\n  "title": "Judul Viral",\n  "description": "Deskripsi panjang...",\n  "tags": ["tag1", "tag2", "tag3"]\n}`;

  const response = await openai.chat.completions.create({
    model: "gpt-4o", 
    messages: [{ role: "user", content: prompt }]
  });

  let text = response.choices[0].message.content;
  text = text.replace(/```json/gi, '').replace(/```/gi, '').trim();
  return JSON.parse(text);
}

async function uploadToYouTube(videoPath, seoData) {
  const res = await youtube.videos.insert({
    part: 'snippet,status',
    requestBody: {
      snippet: {
        title: seoData.title,
        description: seoData.description,
        tags: seoData.tags,
        categoryId: '22'
      },
      status: {
        privacyStatus: 'public', 
        selfDeclaredMadeForKids: false
      }
    },
    media: { body: fs.createReadStream(videoPath) }
  });

  return res.data.id;
}

main();
