import { StatusBar } from 'expo-status-bar';
import * as SecureStore from 'expo-secure-store';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import * as IntentLauncher from 'expo-intent-launcher';
import Constants from 'expo-constants';
import { LinearGradient } from 'expo-linear-gradient';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Animated,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Linking,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'https://neuraai.up.railway.app';
const APP_VERSION: string = Constants.expoConfig?.version ?? '1.0.0';

function isNewer(v1: string, v2: string): boolean {
  const a = v1.split('.').map((n) => parseInt(n || '0', 10) || 0);
  const b = v2.split('.').map((n) => parseInt(n || '0', 10) || 0);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d !== 0) return d > 0;
  }
  return false;
}

const C = {
  bg: '#060a14',
  surface: '#0d1526',
  surface2: '#111b30',
  surface3: '#162139',
  border: '#1c2a45',
  text: '#eaf0fb',
  muted: '#8b98b5',
  accent1: '#6d5cff',
  accent2: '#00d4ff',
  accent3: '#ff6ec7',
};

const CHIPS = [
  { t: 'Neura AI kim?', e: '💬' },
  { t: "O'zbek taomlari", e: '🍲' },
  { t: 'Navro\'z nima?', e: '🌷' },
  { t: 'Rasm tahlil qil', e: '📷' },
];

interface Msg {
  id: number;
  role: 'user' | 'ai';
  text?: string;
  imageUri?: string;
  mediaUrl?: string;
  mediaKind?: 'image' | 'video';
  source?: string;
}

let nextId = 1;

export default function App() {
  return (
    <SafeAreaProvider>
      <Chat />
    </SafeAreaProvider>
  );
}

function Chat() {
  const insets = useSafeAreaInsets();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [uid, setUid] = useState('');
  const convRef = useRef<string | null>(null);
  const uidRef = useRef('');
  const busyRef = useRef(false);
  const listRef = useRef<FlatList<Msg>>(null);
  const pulse = useRef(new Animated.Value(0)).current;
  const [updateInfo, setUpdateInfo] = useState<{ version: string; url: string; size?: number } | null>(null);
  const [updateProgress, setUpdateProgress] = useState<number | null>(null);
  const updateRef = useRef<{ version: string; url: string; size?: number } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        let id = await SecureStore.getItemAsync('neura_uid');
        if (!id) {
          id = `mobile_${Math.random().toString(16).slice(2, 14)}`;
          await SecureStore.setItemAsync('neura_uid', id);
        }
        uidRef.current = id;
        setUid(id);
        const savedConv = await SecureStore.getItemAsync('neura_conv');
        if (savedConv) convRef.current = savedConv;
      } catch {
        uidRef.current = `mobile_${Math.random().toString(16).slice(2, 14)}`;
        setUid(uidRef.current);
      }
    })();
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 2200, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 2200, useNativeDriver: true }),
      ])
    ).start();
    checkUpdate();
  }, [pulse]);

  const checkUpdate = async () => {
    try {
      const res = await fetch(API_BASE + '/api/version', {
        headers: { 'User-Agent': 'NeuraAI-Mobile' },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.version && data.apk_url && isNewer(data.version, APP_VERSION)) {
        updateRef.current = { version: data.version, url: data.apk_url, size: data.size };
        setUpdateInfo(updateRef.current);
      }
    } catch {
      /* offline — e'tiborsiz */
    }
  };

  const installUpdate = async () => {
    const info = updateRef.current;
    if (!info) return;
    try {
      setUpdateProgress(0);
      const fileUri = (FileSystem.cacheDirectory ?? '') + 'neuraai-update.apk';
      const dl = FileSystem.createDownloadResumable(
        info.url,
        fileUri,
        {},
        (p) => {
          const total = p.totalBytesExpectedToWrite;
          if (total > 0) setUpdateProgress(Math.min(1, p.totalBytesWritten / total));
        }
      );
      const result = await dl.downloadAsync();
      if (!result || result.status !== 200) {
        setUpdateProgress(null);
        Alert.alert('Xato', 'Yuklab olish muvaffaqiyatsiz tugadi.');
        return;
      }
      setUpdateProgress(null);
      if (Platform.OS === 'android') {
        const contentUri = await FileSystem.getContentUriAsync(result.uri);
        await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
          data: contentUri,
          type: 'application/vnd.android.package-archive',
          flags: 1,
        });
      } else {
        Alert.alert('Yangilanish', 'Yangi versiyani veb-saytdan yuklab oling');
      }
    } catch {
      setUpdateProgress(null);
      Alert.alert('Xato', 'Yangilash amalga oshmadi. Keyinroq urinib ko\'ring.');
    }
  };

  const addMsg = useCallback((m: Omit<Msg, 'id'>) => {
    setMessages((prev) => [...prev, { ...m, id: nextId++ }]);
  }, []);

  const post = async (path: string, body: unknown) => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  };

  const sendText = async (text: string) => {
    const clean = text.trim();
    if (!clean || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setInput('');
    addMsg({ role: 'user', text: clean });
    try {
      const data = await post('/api/chat', {
        message: clean,
        telegram_id: uidRef.current,
        conversation_id: convRef.current ? Number(convRef.current) : null,
      });
      convRef.current = String(data.conversation_id);
      SecureStore.setItemAsync('neura_conv', String(data.conversation_id)).catch(() => {});
      addMsg({ role: 'ai', text: data.reply, source: data.source });
    } catch (e) {
      addMsg({
        role: 'ai',
        text: "Uzr, tarmoq xatosi yuz berdi. Internetni tekshirib qayta urinib ko'ring.",
        source: 'error',
      });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const sendImage = async () => {
    if (busyRef.current) return;
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('Ruxsat kerak', 'Rasm tahlili uchun galereyaga kirish ruxsati kerak.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.85,
      allowsEditing: false,
    });
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    busyRef.current = true;
    setBusy(true);
    addMsg({ role: 'user', imageUri: asset.uri });
    try {
      const form = new FormData();
      form.append('file', {
        uri: asset.uri,
        name: asset.fileName ?? 'photo.jpg',
        type: asset.mimeType ?? 'image/jpeg',
      } as unknown as Blob);
      const res = await fetch(`${API_BASE}/api/analyze-image`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      addMsg({ role: 'ai', text: formatAnalysis(data), source: 'vision' });
    } catch {
      addMsg({ role: 'ai', text: "Rasmni tahlil qilib bo'lmadi. Qayta urinib ko'ring.", source: 'error' });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const genImage = async () => {
    const prompt = input.trim();
    if (!prompt || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setInput('');
    addMsg({ role: 'user', text: `🎨 ${prompt}` });
    addMsg({ role: 'ai', text: 'Rasm chizilmoqda, biroz kuting...', source: 'pending' });
    try {
      const data = await post('/api/gen/image', { prompt });
      if (data.url) {
        addMsg({
          role: 'ai',
          mediaUrl: API_BASE + data.url,
          mediaKind: 'image',
          text: prompt,
          source: 'gen',
        });
      } else {
        addMsg({ role: 'ai', text: "Rasm chiza olmadim. Qayta urinib ko'ring.", source: 'error' });
      }
    } catch {
      addMsg({ role: 'ai', text: "Rasm chiza olmadim. Internetni tekshiring.", source: 'error' });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const clearChat = () => {
    convRef.current = null;
    SecureStore.deleteItemAsync('neura_conv').catch(() => {});
    setMessages([]);
  };

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <Header insets={insets} pulse={pulse} onClear={clearChat} />
      {updateInfo ? (
        <TouchableOpacity style={styles.updateBar} onPress={installUpdate} activeOpacity={0.8}>
          {updateProgress === null ? (
            <View style={styles.updateRow}>
              <Text style={styles.updateText}>📲 Yangi versiya v{updateInfo.version} chiqdi</Text>
              <Text style={styles.updateAction}>Yangilash</Text>
            </View>
          ) : (
            <View style={styles.updateRow}>
              <Text style={styles.updateText}>
                Yuklanmoqda… {Math.round(updateProgress * 100)}%
              </Text>
              <View style={styles.updateTrack}>
                <View style={[styles.updateFill, { width: `${Math.round(updateProgress * 100)}%` }]} />
              </View>
            </View>
          )}
        </TouchableOpacity>
      ) : null}
      <KeyboardAvoidingView
        style={styles.body}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        <FlatList
          ref={listRef}
          style={styles.list}
          data={messages}
          keyExtractor={(m) => String(m.id)}
          renderItem={({ item }) => <MsgBubble m={item} />}
          ListEmptyComponent={<Welcome pulse={pulse} onChip={sendText} onAnalyze={sendImage} onGen={genImage} />}
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          ListFooterComponent={busy ? <Typing /> : null}
        />
        <InputBar
          insets={insets}
          value={input}
          onChange={setInput}
          onSend={() => sendText(input)}
          onImage={sendImage}
          onGen={genImage}
          busy={busy}
        />
      </KeyboardAvoidingView>
    </View>
  );
}

function Header({ insets, pulse, onClear }: { insets: any; pulse: Animated.Value; onClear: () => void }) {
  const glow = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] });
  return (
    <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
      <View style={styles.headerLeft}>
        <View style={styles.headerLogoWrap}>
          <LinearGradient colors={[C.accent1, C.accent2]} style={styles.headerLogo} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
            <Animated.View style={[styles.headerGlow, { opacity: glow }]} />
            <Text style={styles.headerLogoText}>N</Text>
          </LinearGradient>
        </View>
        <View>
          <Text style={styles.headerTitle}>Neura AI</Text>
          <View style={styles.onlineRow}>
            <View style={styles.onlineDot} />
            <Text style={styles.headerSub}>AI yordamchi · onlayn</Text>
          </View>
        </View>
      </View>
      <TouchableOpacity onPress={onClear} style={styles.headerBtn} hitSlop={10}>
        <Text style={styles.headerBtnText}>🗑</Text>
      </TouchableOpacity>
    </View>
  );
}

function Welcome({
  pulse,
  onChip,
  onAnalyze,
  onGen,
}: {
  pulse: Animated.Value;
  onChip: (t: string) => void;
  onAnalyze: () => void;
  onGen: () => void;
}) {
  const glow = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.25, 0.8] });
  const FEATURES = [
    { e: '💬', t: 'Suhbat', d: 'O\'zbek tilida javob', g: ['#6d5cff', '#8f7bff'] },
    { e: '💻', t: 'Kod', d: 'Dasturlash kodlari', g: ['#0ea5e9', '#00d4ff'] },
    { e: '🌍', t: 'Qidiruv', d: 'Internet ma\'lumoti', g: ['#10b981', '#34d399'] },
    { e: '🎨', t: 'Rasm yarat', d: 'Promptdan rasm', g: ['#f472b6', '#ff6ec7'] },
  ];
  return (
    <View style={styles.welcome}>
      <View style={styles.logoOuter}>
        <Animated.View style={[styles.logoGlow, { opacity: glow }]} />
        <LinearGradient
          colors={[C.accent1, C.accent2]}
          style={styles.logo}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <Text style={styles.logoText}>N</Text>
        </LinearGradient>
      </View>
      <Text style={styles.welcomeTitle}>Assalomu alaykum!</Text>
      <Text style={styles.welcomeSub}>
        Neura AI — o'zbek tilidagi sun'iy intellekt yordamchingiz.{'\n'}
        Savol bering, rasm tahlil qiling yoki rasm chizdirib ko'ring.
      </Text>
      <View style={styles.featGrid}>
        {FEATURES.map((f) => (
          <TouchableOpacity
            key={f.t}
            style={[styles.featCard, { borderTopColor: f.g[1] }]}
            onPress={f.t === 'Rasm yarat' ? onGen : () => onChip('Neura AI nima qila oladi?')}
            activeOpacity={0.7}
          >
            <LinearGradient colors={f.g as [string, string]} style={styles.featEmojiWrap} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
              <Text style={styles.featEmoji}>{f.e}</Text>
            </LinearGradient>
            <Text style={styles.featTitle}>{f.t}</Text>
            <Text style={styles.featDesc}>{f.d}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.chipsWrap}>
        {CHIPS.map((chip) => (
          <TouchableOpacity
            key={chip.t}
            style={styles.chip}
            onPress={chip.t.startsWith('Rasm tahlil') ? onAnalyze : () => onChip(chip.t)}
            activeOpacity={0.7}
          >
            <Text style={styles.chipText}>{chip.e} {chip.t}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

function MsgBubble({ m }: { m: Msg }) {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.parallel([
      Animated.timing(anim, { toValue: 1, duration: 260, useNativeDriver: true }),
      Animated.spring(anim, { toValue: 1, friction: 8, useNativeDriver: true }),
    ]).start();
  }, [anim]);
  const translateY = anim.interpolate({ inputRange: [0, 1], outputRange: [14, 0] });
  const opacity = anim.interpolate({ inputRange: [0, 1], outputRange: [0, 1] });

  const sourceLabel =
    m.source === 'llm' ? 'AI' : m.source === 'facts' ? 'Bilim' : m.source === 'vision' ? 'Tahlil' : m.source === 'gen' ? 'Rasm' : null;

  return (
    <Animated.View
      style={[
        styles.msgRow,
        m.role === 'user' ? styles.msgRowUser : styles.msgRowAi,
        { opacity, transform: [{ translateY }] },
      ]}
    >
      {m.role === 'ai' && (
        <View style={styles.aiAvatar}>
          <LinearGradient colors={[C.accent1, C.accent2]} style={styles.aiAvatarGrad}>
            <Text style={styles.aiAvatarText}>✦</Text>
          </LinearGradient>
        </View>
      )}
      <View style={m.role === 'user' ? styles.userBubbleWrap : styles.aiBubbleWrap}>
        {m.imageUri && (
          <Image source={{ uri: m.imageUri }} style={styles.bubbleImage} resizeMode="cover" />
        )}
        {m.mediaUrl && m.mediaKind === 'image' && (
          <Image source={{ uri: m.mediaUrl }} style={styles.bubbleImage} resizeMode="cover" />
        )}
        {m.mediaUrl && m.mediaKind === 'video' && (
          <TouchableOpacity
            style={styles.videoBox}
            onPress={() => Linking.openURL(m.mediaUrl!).catch(() => {})}
          >
            <Text style={styles.videoBoxEmoji}>🎬</Text>
            <Text style={styles.videoBoxText}>Videoni ochish</Text>
          </TouchableOpacity>
        )}
        {!!m.text && (
          m.role === 'user' ? (
            <LinearGradient
              colors={[C.accent1, C.accent2]}
              style={styles.gradBubble}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
            >
              <Text style={styles.userText}>{m.text}</Text>
            </LinearGradient>
          ) : (
            <View style={styles.aiBubbleWrap}>
              <Text style={styles.aiText}>{m.text}</Text>
            </View>
          )
        )}
        {m.role === 'ai' && sourceLabel && (
          <View style={styles.sourceBadge}>
            <Text style={styles.sourceText}>{sourceLabel}</Text>
          </View>
        )}
      </View>
    </Animated.View>
  );
}

function Typing() {
  const dots = [useRef(new Animated.Value(0)).current, useRef(new Animated.Value(0)).current, useRef(new Animated.Value(0)).current];
  useEffect(() => {
    const anims = dots.map((d, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 180),
          Animated.timing(d, { toValue: 1, duration: 420, useNativeDriver: true }),
          Animated.timing(d, { toValue: 0, duration: 420, useNativeDriver: true }),
          Animated.delay((2 - i) * 180),
        ])
      )
    );
    anims.forEach((a) => a.start());
    return () => anims.forEach((a) => a.stop());
  }, [dots]);
  return (
    <View style={styles.msgRowAi}>
      <View style={styles.aiAvatar}>
        <LinearGradient colors={[C.accent1, C.accent2]} style={styles.aiAvatarGrad}>
          <Text style={styles.aiAvatarText}>✦</Text>
        </LinearGradient>
      </View>
      <View style={[styles.aiBubbleWrap, styles.typingBubble]}>
        {dots.map((d, i) => (
          <Animated.View
            key={i}
            style={[styles.typingDot, { opacity: d.interpolate({ inputRange: [0, 1], outputRange: [0.3, 1] }) }]}
          />
        ))}
      </View>
    </View>
  );
}

function InputBar({
  insets,
  value,
  onChange,
  onSend,
  onImage,
  onGen,
  busy,
}: {
  insets: any;
  value: string;
  onChange: (t: string) => void;
  onSend: () => void;
  onImage: () => void;
  onGen: () => void;
  busy: boolean;
}) {
  const canSend = value.trim().length > 0 && !busy;
  return (
    <View style={[styles.inputWrap, { paddingBottom: Math.max(insets.bottom, 10) }]}>
      <View style={styles.inputRow}>
        <TouchableOpacity style={styles.inputBtn} onPress={onImage} disabled={busy} hitSlop={6}>
          <Text style={styles.inputBtnText}>🖼</Text>
        </TouchableOpacity>
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={onChange}
          placeholder={busy ? "AI javob yozmoqda..." : 'Xabar yozing...'}
          placeholderTextColor={C.muted}
          multiline
          maxLength={1000}
        />
        {!busy && value.trim().length > 0 && (
          <TouchableOpacity style={styles.inputBtn} onPress={onGen} disabled={busy} hitSlop={6}>
            <Text style={styles.inputBtnText}>🎨</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity onPress={onSend} disabled={!canSend} activeOpacity={0.8} hitSlop={6}>
          <LinearGradient
            colors={canSend ? [C.accent1, C.accent2] : ['#223050', '#223050']}
            style={styles.sendBtn}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
          >
            <Text style={[styles.sendText, !canSend && { color: '#5a6a8d' }]}>➤</Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function formatAnalysis(d: any): string {
  const lines: string[] = ['🖼 Rasm tahlili:'];
  lines.push(`• Format: ${d.format}`);
  lines.push(`• O'lcham: ${d.width} × ${d.height}`);
  lines.push(`• Yorug'lik: ${d.brightness}`);
  if (Array.isArray(d.colors) && d.colors.length) {
    lines.push(`• Ranglar: ${d.colors.map((c: any) => `${c.name} ${c.percent}%`).join(', ')}`);
  }
  lines.push(`• Nozik soyalar: ${d.unique_colors}`);
  lines.push(`• Fotosuratga o'xshaydi: ${d.photo_like ? 'ha' : "yo'q"}`);
  const exif = d.exif || {};
  const exifParts = [
    exif.Make && exif.Model ? `${exif.Make} ${exif.Model}` : exif.Make || exif.Model,
    exif.DateTimeOriginal,
  ].filter(Boolean);
  if (exifParts.length) lines.push(`• EXIF: ${exifParts.join(', ')}`);
  return lines.join('\n');
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  body: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: C.surface,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerLogoWrap: {
    width: 40,
    height: 40,
    borderRadius: 14,
    padding: 2,
    backgroundColor: 'transparent',
  },
  headerLogo: {
    flex: 1,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  headerGlow: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(255,255,255,0.25)',
  },
  headerLogoText: { color: '#fff', fontSize: 22, fontWeight: '800' },
  headerTitle: { color: C.text, fontSize: 17, fontWeight: '700' },
  onlineRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 1 },
  onlineDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#3ddc84' },
  headerSub: { color: C.muted, fontSize: 12 },
  headerBtn: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: C.surface2,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerBtnText: { fontSize: 16 },
  list: { flex: 1 },
  listContent: { padding: 14, flexGrow: 1 },
  welcome: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 30 },
  logoOuter: { width: 110, height: 110, marginBottom: 22, alignItems: 'center', justifyContent: 'center' },
  logoGlow: {
    position: 'absolute',
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: C.accent1,
    opacity: 0.3,
    transform: [{ scale: 1.25 }],
  },
  logo: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.18)',
  },
  logoText: { color: '#fff', fontSize: 52, fontWeight: '800' },
  welcomeTitle: { color: C.text, fontSize: 22, fontWeight: '800', marginBottom: 8 },
  welcomeSub: {
    color: C.muted,
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 21,
    paddingHorizontal: 28,
    marginBottom: 24,
  },
  chipsWrap: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 10, paddingHorizontal: 18 },
  featGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 10,
    paddingHorizontal: 18,
    marginBottom: 22,
  },
  featCard: {
    width: '46%',
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.border,
    borderTopWidth: 2,
    borderRadius: 18,
    paddingVertical: 16,
    paddingHorizontal: 14,
    alignItems: 'center',
  },
  featEmojiWrap: {
    width: 44,
    height: 44,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  featEmoji: { fontSize: 22 },
  featTitle: { color: C.text, fontSize: 14, fontWeight: '700' },
  featDesc: { color: C.muted, fontSize: 11.5, marginTop: 2, textAlign: 'center' },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 22,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.border,
  },
  chipText: { color: C.text, fontSize: 13.5, fontWeight: '600' },
  msgRow: { flexDirection: 'row', marginBottom: 14, alignItems: 'flex-end' },
  msgRowUser: { justifyContent: 'flex-end' },
  msgRowAi: { justifyContent: 'flex-start', gap: 9 },
  aiAvatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    padding: 1.5,
    backgroundColor: 'transparent',
  },
  aiAvatarGrad: {
    flex: 1,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  aiAvatarText: { color: '#fff', fontSize: 13 },
  userBubbleWrap: { maxWidth: '82%' },
  gradBubble: {
    borderRadius: 18,
    borderBottomRightRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  aiBubbleWrap: {
    maxWidth: '78%',
    borderRadius: 18,
    borderTopLeftRadius: 6,
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: C.surface,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  userBubbleOuter: { overflow: 'hidden', borderRadius: 18, borderBottomRightRadius: 6 },
  userText: { color: '#fff', fontSize: 15.5, lineHeight: 22, fontWeight: '600' },
  aiText: { color: C.text, fontSize: 15.5, lineHeight: 22 },
  sourceBadge: { alignSelf: 'flex-start', marginTop: 5, marginLeft: 2 },
  sourceText: { color: C.accent2, fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  bubbleImage: { width: 230, height: 190, borderRadius: 16, marginBottom: 6 },
  videoBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.surface2,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 4,
  },
  videoBoxEmoji: { fontSize: 18 },
  videoBoxText: { color: C.text, fontWeight: '600', fontSize: 14 },
  typingBubble: { flexDirection: 'row', gap: 6, alignItems: 'center', paddingVertical: 15, paddingHorizontal: 18 },
  typingDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.accent2 },
  updateBar: {
    backgroundColor: C.surface2,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  updateRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  updateText: { color: C.text, fontSize: 13, flex: 1 },
  updateAction: {
    color: '#0a0e1a',
    backgroundColor: C.accent2,
    fontWeight: '700',
    fontSize: 13,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    overflow: 'hidden',
  },
  updateTrack: { flex: 1, height: 6, borderRadius: 3, backgroundColor: C.border, overflow: 'hidden' },
  updateFill: { height: 6, borderRadius: 3, backgroundColor: C.accent2 },
  inputWrap: { backgroundColor: C.surface, borderTopWidth: 1, borderTopColor: C.border, paddingTop: 10 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: 12,
    borderRadius: 26,
  },
  inputBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: C.surface2,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 2,
  },
  inputBtnText: { fontSize: 17 },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    color: C.text,
    fontSize: 15.5,
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: C.surface2,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: C.border,
  },
  sendBtn: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 2,
  },
  sendText: { color: '#fff', fontSize: 18, fontWeight: '700', marginLeft: 2 },
});
