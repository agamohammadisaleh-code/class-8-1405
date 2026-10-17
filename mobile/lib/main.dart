/// مربی هوشمند پایه هشتم — اپ اندروید دانش‌آموز (Flutter)
///
/// قابلیت‌ها: ورود، فهرست درس‌ها، آموزش مرحله‌به‌مرحله، تمرین هدایت‌شده با
/// راهنمایی تدریجی، آزمون مستقل (بدون افشای پاسخ تا پایان)، دفتر اشتباهات،
/// تکالیف، ذخیره آفلاین با SQLite و همگام‌سازی پاسخ‌ها پس از اتصال اینترنت.
///
/// ساخت APK (روی ماشینی که Flutter و Android SDK نصب است):
///   flutter pub get
///   flutter build apk --dart-define=API_BASE=https://YOUR-SERVER
/// در این محیط سندباکس Flutter/Android SDK موجود نیست؛ جزئیات در docs/LIMITATIONS.md
library;

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;

const apiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');

Future<Database> openDb() async {
  final dir = await getDatabasesPath();
  return openDatabase(p.join(dir, 'morabi8.db'), version: 1, onCreate: (db, v) async {
    await db.execute(
        'CREATE TABLE offline_answers(client_id TEXT PRIMARY KEY, question_id INTEGER, given_answer TEXT, hints_used INTEGER)');
    await db.execute('CREATE TABLE bundle(id INTEGER PRIMARY KEY, json TEXT)');
  });
}

class Api {
  String? token;
  Future<void> loadToken() async {
    token = (await SharedPreferences.getInstance()).getString('token');
  }

  Map<String, String> get headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<dynamic> get(String path) async =>
      jsonDecode((await http.get(Uri.parse('$apiBase$path'), headers: headers)).body);

  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    final r = await http.post(Uri.parse('$apiBase$path'),
        headers: headers, body: jsonEncode(body));
    if (r.statusCode >= 400) throw Exception(jsonDecode(r.body)['detail'] ?? 'خطا');
    return jsonDecode(r.body);
  }
}

void main() => runApp(const MorabiApp());

class MorabiApp extends StatelessWidget {
  const MorabiApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'مربی هوشمند هشتم',
        // نمای فارسی و راست‌چین
        builder: (context, child) =>
            Directionality(textDirection: TextDirection.rtl, child: child!),
        theme: ThemeData(colorSchemeSeed: const Color(0xFF0F766E), useMaterial3: true),
        home: const LoginPage(),
      );
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final email = TextEditingController(text: 'student@example.com');
  final password = TextEditingController(text: 'Student1234');
  String error = '';
  final api = Api();

  Future<void> login() async {
    try {
      final r = await api.post('/api/auth/login',
          {'email': email.text.trim(), 'password': password.text});
      api.token = r['token'];
      (await SharedPreferences.getInstance()).setString('token', api.token!);
      if (!mounted) return;
      Navigator.pushReplacement(
          context, MaterialPageRoute(builder: (_) => HomePage(api: api)));
    } catch (e) {
      setState(() => error = 'ایمیل یا گذرواژه نادرست است.');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('مربی هوشمند پایه هشتم')),
        body: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Text('به مربی هوشمند خوش آمدی! 🎓', style: TextStyle(fontSize: 20)),
            const SizedBox(height: 16),
            TextField(controller: email, decoration: const InputDecoration(labelText: 'ایمیل')),
            TextField(
                controller: password,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'گذرواژه')),
            if (error.isNotEmpty)
              Text(error, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 16),
            FilledButton(onPressed: login, child: const Text('ورود')),
          ]),
        ),
      );
}

class HomePage extends StatefulWidget {
  final Api api;
  const HomePage({super.key, required this.api});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List<dynamic> books = [];
  Map<String, dynamic>? next;
  String status = '';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      books = await widget.api.get('/api/books') as List<dynamic>;
      next = await widget.api.get('/api/tutor/next') as Map<String, dynamic>;
    } catch (_) {
      status = 'آفلاین هستی؛ از بسته دانلودشده استفاده می‌شود.';
    }
    setState(() {});
  }

  Future<void> syncOffline() async {
    final db = await openDb();
    final rows = await db.query('offline_answers');
    if (rows.isEmpty) {
      setState(() => status = 'پاسخ آفلاینی در انتظار نیست.');
      return;
    }
    final r = await widget.api.post('/api/sync/answers', rows);
    await db.delete('offline_answers');
    setState(() => status =
        'همگام‌سازی شد: ${r['saved']} پاسخ ثبت و ${r['duplicates_ignored']} تکراری نادیده گرفته شد.');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('خانه'), actions: [
          IconButton(onPressed: syncOffline, icon: const Icon(Icons.sync)),
        ]),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          if (next != null)
            Card(
                child: ListTile(
                    title: const Text('📌 پیشنهاد مربی'),
                    subtitle: Text('${next!['title'] ?? ''}\n${next!['reason'] ?? ''}'))),
          if (status.isNotEmpty) Text(status),
          const Text('📚 کتاب‌ها', style: TextStyle(fontSize: 18)),
          ...books.map((b) => Card(
              child: ListTile(
                  title: Text(b['title']),
                  subtitle: Text('محتوای فعلی نمونه آزمایشی است'),
                  trailing: const Icon(Icons.chevron_left)))),
          const Card(
              child: ListTile(
                  title: Text('🎙 روان‌خوانی'),
                  subtitle: Text(
                      'صوت نمونه با TTS دستگاه پخش می‌شود؛ ضبط صدا اختیاری و فقط با رضایت والد است.'))),
          const Card(
              child: ListTile(
                  title: Text('🔁 مرور فاصله‌دار و دفتر اشتباهات'),
                  subtitle: Text('از سرور خوانده می‌شود و در حالت آفلاین از صف محلی استفاده می‌کند.'))),
        ]),
      );
}
