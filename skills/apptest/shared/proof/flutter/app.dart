// Proof app: small on purpose. Each flag in Bugs switches on one deliberate defect.
import 'dart:convert';

import 'package:clock/clock.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class Order {
  const Order(this.amount);
  final String amount;
}

abstract class OrderRepo {
  Future<void> save(Order o);
}

class Bugs {
  const Bugs({this.crash = false, this.a11y = false, this.doubleSave = false, this.deadEnd = false,
      this.afterDispose = false, this.workOnResume = false});
  final bool crash, a11y, doubleSave, deadEnd, afterDispose, workOnResume;
}

Widget buildApp(OrderRepo repo, {Bugs bugs = const Bugs(), bool formFirst = false}) => MaterialApp(
      initialRoute: formFirst ? '/form' : '/',
      routes: {
        '/': (_) => HomePage(bugs: bugs),
        '/form': (_) => FormPage(repo: repo, bugs: bugs),
      },
    );

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.bugs});
  final Bugs bugs;
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  var saved = 0;

  Future<void> _open() async {
    if (widget.bugs.deadEnd) return; // planned bug: the main button does nothing
    final done = await Navigator.of(context).pushNamed('/form');
    if (done == true && mounted) setState(() => saved++);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Orders')),
        body: SingleChildScrollView(
          child: Column(children: [
            Text('Saved $saved', key: const Key('saved')),
            ElevatedButton(key: const Key('add'), onPressed: _open, child: const Text('Add order')),
            if (widget.bugs.crash)
              ElevatedButton(onPressed: () => throw StateError('planned crash'), child: const Text('Reports')),
            if (widget.bugs.a11y) IconButton(onPressed: () {}, icon: const Icon(Icons.settings)),
          ]),
        ),
      );
}

class FormPage extends StatefulWidget {
  const FormPage({super.key, required this.repo, required this.bugs});
  final OrderRepo repo;
  final Bugs bugs;
  @override
  State<FormPage> createState() => _FormPageState();
}

class _FormPageState extends State<FormPage> with WidgetsBindingObserver {
  final _amount = TextEditingController();
  final _note = TextEditingController();
  var _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // planned bug: returning from the background repeats work
    if (widget.bugs.workOnResume && state == AppLifecycleState.resumed) widget.repo.save(const Order('again'));
  }

  Future<void> _save() async {
    if (_busy && !widget.bugs.doubleSave) return;
    setState(() => _busy = true);
    await widget.repo.save(Order(_amount.text));
    if (widget.bugs.afterDispose) {
      setState(() => _busy = false); // planned bug: no mounted check
      return;
    }
    if (mounted) Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('New order')),
        body: SingleChildScrollView(
          child: Column(children: [
            TextField(key: const Key('amount'), controller: _amount, decoration: const InputDecoration(labelText: 'Amount')),
            TextField(key: const Key('note'), controller: _note, decoration: const InputDecoration(labelText: 'Note')),
            ElevatedButton(key: const Key('save'), onPressed: _busy && !widget.bugs.doubleSave ? null : _save, child: const Text('Save')),
          ]),
        ),
      );
}

/// Network status for the fault templates: a bad reply must become a message, not a crash.
Future<String> fetchStatus(http.Client client, {bool bug = false}) async {
  try {
    final r = await client.get(Uri.parse('https://proof.invalid/ping'));
    if (r.statusCode >= 500) return 'try again';
    if (bug) return (jsonDecode(r.body) as Map)['ok'].toString(); // planned bug: bad JSON escapes
    try {
      return (jsonDecode(r.body) as Map)['ok'].toString();
    } on FormatException {
      return 'try again';
    }
  } on http.ClientException {
    return 'try again';
  }
}

/// One write per key, however many times it is asked for.
class Writer {
  Writer({this.bug = false});
  final bool bug;
  final rows = <String>{};
  final list = <String>[];
  Future<void> addExpense(String e) async {
    if (!bug && rows.contains(e)) return;
    rows.add(e);
    await Future<void>.delayed(Duration.zero);
    list.add(e);
  }
}

bool isDueToday(DateTime due) {
  final n = clock.now();
  return n.year == due.year && n.month == due.month && n.day == due.day;
}

int daysBetween(DateTime a, DateTime b, {bool bug = false}) =>
    bug ? b.difference(a).inDays : DateTime.utc(b.year, b.month, b.day).difference(DateTime.utc(a.year, a.month, a.day)).inDays;
