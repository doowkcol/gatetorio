// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:gatetorio_app/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const GateterioApp());

    // Verify that the app title is present
    expect(find.text('Gatetorio Gate Controller'), findsOneWidget);

    // Verify that device scanner elements are present
    expect(find.text('Find Your Gate Controller'), findsOneWidget);
    expect(find.text('Start Scanning'), findsOneWidget);
  });
}
