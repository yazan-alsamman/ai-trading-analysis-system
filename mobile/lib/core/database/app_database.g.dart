// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $CachedQuotesTable extends CachedQuotes
    with TableInfo<$CachedQuotesTable, CachedQuoteRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedQuotesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _symbolMeta = const VerificationMeta('symbol');
  @override
  late final GeneratedColumn<String> symbol = GeneratedColumn<String>(
      'symbol', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _priceMeta = const VerificationMeta('price');
  @override
  late final GeneratedColumn<double> price = GeneratedColumn<double>(
      'price', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _changeMeta = const VerificationMeta('change');
  @override
  late final GeneratedColumn<double> change = GeneratedColumn<double>(
      'change', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _updatedAtMeta =
      const VerificationMeta('updatedAt');
  @override
  late final GeneratedColumn<int> updatedAt = GeneratedColumn<int>(
      'updated_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns => [symbol, price, change, updatedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_quotes';
  @override
  VerificationContext validateIntegrity(Insertable<CachedQuoteRow> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('symbol')) {
      context.handle(_symbolMeta,
          symbol.isAcceptableOrUnknown(data['symbol']!, _symbolMeta));
    } else if (isInserting) {
      context.missing(_symbolMeta);
    }
    if (data.containsKey('price')) {
      context.handle(
          _priceMeta, price.isAcceptableOrUnknown(data['price']!, _priceMeta));
    } else if (isInserting) {
      context.missing(_priceMeta);
    }
    if (data.containsKey('change')) {
      context.handle(_changeMeta,
          change.isAcceptableOrUnknown(data['change']!, _changeMeta));
    } else if (isInserting) {
      context.missing(_changeMeta);
    }
    if (data.containsKey('updated_at')) {
      context.handle(_updatedAtMeta,
          updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta));
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {symbol};
  @override
  CachedQuoteRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedQuoteRow(
      symbol: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}symbol'])!,
      price: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}price'])!,
      change: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}change'])!,
      updatedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}updated_at'])!,
    );
  }

  @override
  $CachedQuotesTable createAlias(String alias) {
    return $CachedQuotesTable(attachedDatabase, alias);
  }
}

class CachedQuoteRow extends DataClass implements Insertable<CachedQuoteRow> {
  final String symbol;
  final double price;

  /// التغيّر خلال 24 ساعة (السعر - سعر قبل 24 ساعة)
  final double change;

  /// وقت السعر نفسه (ms UTC) = "Last updated"
  final int updatedAt;
  const CachedQuoteRow(
      {required this.symbol,
      required this.price,
      required this.change,
      required this.updatedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['symbol'] = Variable<String>(symbol);
    map['price'] = Variable<double>(price);
    map['change'] = Variable<double>(change);
    map['updated_at'] = Variable<int>(updatedAt);
    return map;
  }

  CachedQuotesCompanion toCompanion(bool nullToAbsent) {
    return CachedQuotesCompanion(
      symbol: Value(symbol),
      price: Value(price),
      change: Value(change),
      updatedAt: Value(updatedAt),
    );
  }

  factory CachedQuoteRow.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedQuoteRow(
      symbol: serializer.fromJson<String>(json['symbol']),
      price: serializer.fromJson<double>(json['price']),
      change: serializer.fromJson<double>(json['change']),
      updatedAt: serializer.fromJson<int>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'symbol': serializer.toJson<String>(symbol),
      'price': serializer.toJson<double>(price),
      'change': serializer.toJson<double>(change),
      'updatedAt': serializer.toJson<int>(updatedAt),
    };
  }

  CachedQuoteRow copyWith(
          {String? symbol, double? price, double? change, int? updatedAt}) =>
      CachedQuoteRow(
        symbol: symbol ?? this.symbol,
        price: price ?? this.price,
        change: change ?? this.change,
        updatedAt: updatedAt ?? this.updatedAt,
      );
  CachedQuoteRow copyWithCompanion(CachedQuotesCompanion data) {
    return CachedQuoteRow(
      symbol: data.symbol.present ? data.symbol.value : this.symbol,
      price: data.price.present ? data.price.value : this.price,
      change: data.change.present ? data.change.value : this.change,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedQuoteRow(')
          ..write('symbol: $symbol, ')
          ..write('price: $price, ')
          ..write('change: $change, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(symbol, price, change, updatedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedQuoteRow &&
          other.symbol == this.symbol &&
          other.price == this.price &&
          other.change == this.change &&
          other.updatedAt == this.updatedAt);
}

class CachedQuotesCompanion extends UpdateCompanion<CachedQuoteRow> {
  final Value<String> symbol;
  final Value<double> price;
  final Value<double> change;
  final Value<int> updatedAt;
  final Value<int> rowid;
  const CachedQuotesCompanion({
    this.symbol = const Value.absent(),
    this.price = const Value.absent(),
    this.change = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CachedQuotesCompanion.insert({
    required String symbol,
    required double price,
    required double change,
    required int updatedAt,
    this.rowid = const Value.absent(),
  })  : symbol = Value(symbol),
        price = Value(price),
        change = Value(change),
        updatedAt = Value(updatedAt);
  static Insertable<CachedQuoteRow> custom({
    Expression<String>? symbol,
    Expression<double>? price,
    Expression<double>? change,
    Expression<int>? updatedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (symbol != null) 'symbol': symbol,
      if (price != null) 'price': price,
      if (change != null) 'change': change,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CachedQuotesCompanion copyWith(
      {Value<String>? symbol,
      Value<double>? price,
      Value<double>? change,
      Value<int>? updatedAt,
      Value<int>? rowid}) {
    return CachedQuotesCompanion(
      symbol: symbol ?? this.symbol,
      price: price ?? this.price,
      change: change ?? this.change,
      updatedAt: updatedAt ?? this.updatedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (symbol.present) {
      map['symbol'] = Variable<String>(symbol.value);
    }
    if (price.present) {
      map['price'] = Variable<double>(price.value);
    }
    if (change.present) {
      map['change'] = Variable<double>(change.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<int>(updatedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedQuotesCompanion(')
          ..write('symbol: $symbol, ')
          ..write('price: $price, ')
          ..write('change: $change, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CachedCandlesTable extends CachedCandles
    with TableInfo<$CachedCandlesTable, CachedCandleRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedCandlesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
      'id', aliasedName, false,
      hasAutoIncrement: true,
      type: DriftSqlType.int,
      requiredDuringInsert: false,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('PRIMARY KEY AUTOINCREMENT'));
  static const VerificationMeta _symbolMeta = const VerificationMeta('symbol');
  @override
  late final GeneratedColumn<String> symbol = GeneratedColumn<String>(
      'symbol', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _timeframeMeta =
      const VerificationMeta('timeframe');
  @override
  late final GeneratedColumn<String> timeframe = GeneratedColumn<String>(
      'timeframe', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _openTimeMeta =
      const VerificationMeta('openTime');
  @override
  late final GeneratedColumn<int> openTime = GeneratedColumn<int>(
      'open_time', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _openMeta = const VerificationMeta('open');
  @override
  late final GeneratedColumn<double> open = GeneratedColumn<double>(
      'open', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _highMeta = const VerificationMeta('high');
  @override
  late final GeneratedColumn<double> high = GeneratedColumn<double>(
      'high', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _lowMeta = const VerificationMeta('low');
  @override
  late final GeneratedColumn<double> low = GeneratedColumn<double>(
      'low', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _closeMeta = const VerificationMeta('close');
  @override
  late final GeneratedColumn<double> close = GeneratedColumn<double>(
      'close', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _volumeMeta = const VerificationMeta('volume');
  @override
  late final GeneratedColumn<double> volume = GeneratedColumn<double>(
      'volume', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns =>
      [id, symbol, timeframe, openTime, open, high, low, close, volume];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_candles';
  @override
  VerificationContext validateIntegrity(Insertable<CachedCandleRow> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('symbol')) {
      context.handle(_symbolMeta,
          symbol.isAcceptableOrUnknown(data['symbol']!, _symbolMeta));
    } else if (isInserting) {
      context.missing(_symbolMeta);
    }
    if (data.containsKey('timeframe')) {
      context.handle(_timeframeMeta,
          timeframe.isAcceptableOrUnknown(data['timeframe']!, _timeframeMeta));
    } else if (isInserting) {
      context.missing(_timeframeMeta);
    }
    if (data.containsKey('open_time')) {
      context.handle(_openTimeMeta,
          openTime.isAcceptableOrUnknown(data['open_time']!, _openTimeMeta));
    } else if (isInserting) {
      context.missing(_openTimeMeta);
    }
    if (data.containsKey('open')) {
      context.handle(
          _openMeta, open.isAcceptableOrUnknown(data['open']!, _openMeta));
    } else if (isInserting) {
      context.missing(_openMeta);
    }
    if (data.containsKey('high')) {
      context.handle(
          _highMeta, high.isAcceptableOrUnknown(data['high']!, _highMeta));
    } else if (isInserting) {
      context.missing(_highMeta);
    }
    if (data.containsKey('low')) {
      context.handle(
          _lowMeta, low.isAcceptableOrUnknown(data['low']!, _lowMeta));
    } else if (isInserting) {
      context.missing(_lowMeta);
    }
    if (data.containsKey('close')) {
      context.handle(
          _closeMeta, close.isAcceptableOrUnknown(data['close']!, _closeMeta));
    } else if (isInserting) {
      context.missing(_closeMeta);
    }
    if (data.containsKey('volume')) {
      context.handle(_volumeMeta,
          volume.isAcceptableOrUnknown(data['volume']!, _volumeMeta));
    } else if (isInserting) {
      context.missing(_volumeMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  CachedCandleRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedCandleRow(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}id'])!,
      symbol: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}symbol'])!,
      timeframe: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}timeframe'])!,
      openTime: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}open_time'])!,
      open: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}open'])!,
      high: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}high'])!,
      low: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}low'])!,
      close: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}close'])!,
      volume: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}volume'])!,
    );
  }

  @override
  $CachedCandlesTable createAlias(String alias) {
    return $CachedCandlesTable(attachedDatabase, alias);
  }
}

class CachedCandleRow extends DataClass implements Insertable<CachedCandleRow> {
  final int id;
  final String symbol;

  /// `Timeframe.apiValue` (1m، 15m، 1h، 4h، 1d)
  final String timeframe;

  /// بداية الشمعة (ms UTC)
  final int openTime;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;
  const CachedCandleRow(
      {required this.id,
      required this.symbol,
      required this.timeframe,
      required this.openTime,
      required this.open,
      required this.high,
      required this.low,
      required this.close,
      required this.volume});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['symbol'] = Variable<String>(symbol);
    map['timeframe'] = Variable<String>(timeframe);
    map['open_time'] = Variable<int>(openTime);
    map['open'] = Variable<double>(open);
    map['high'] = Variable<double>(high);
    map['low'] = Variable<double>(low);
    map['close'] = Variable<double>(close);
    map['volume'] = Variable<double>(volume);
    return map;
  }

  CachedCandlesCompanion toCompanion(bool nullToAbsent) {
    return CachedCandlesCompanion(
      id: Value(id),
      symbol: Value(symbol),
      timeframe: Value(timeframe),
      openTime: Value(openTime),
      open: Value(open),
      high: Value(high),
      low: Value(low),
      close: Value(close),
      volume: Value(volume),
    );
  }

  factory CachedCandleRow.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedCandleRow(
      id: serializer.fromJson<int>(json['id']),
      symbol: serializer.fromJson<String>(json['symbol']),
      timeframe: serializer.fromJson<String>(json['timeframe']),
      openTime: serializer.fromJson<int>(json['openTime']),
      open: serializer.fromJson<double>(json['open']),
      high: serializer.fromJson<double>(json['high']),
      low: serializer.fromJson<double>(json['low']),
      close: serializer.fromJson<double>(json['close']),
      volume: serializer.fromJson<double>(json['volume']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'symbol': serializer.toJson<String>(symbol),
      'timeframe': serializer.toJson<String>(timeframe),
      'openTime': serializer.toJson<int>(openTime),
      'open': serializer.toJson<double>(open),
      'high': serializer.toJson<double>(high),
      'low': serializer.toJson<double>(low),
      'close': serializer.toJson<double>(close),
      'volume': serializer.toJson<double>(volume),
    };
  }

  CachedCandleRow copyWith(
          {int? id,
          String? symbol,
          String? timeframe,
          int? openTime,
          double? open,
          double? high,
          double? low,
          double? close,
          double? volume}) =>
      CachedCandleRow(
        id: id ?? this.id,
        symbol: symbol ?? this.symbol,
        timeframe: timeframe ?? this.timeframe,
        openTime: openTime ?? this.openTime,
        open: open ?? this.open,
        high: high ?? this.high,
        low: low ?? this.low,
        close: close ?? this.close,
        volume: volume ?? this.volume,
      );
  CachedCandleRow copyWithCompanion(CachedCandlesCompanion data) {
    return CachedCandleRow(
      id: data.id.present ? data.id.value : this.id,
      symbol: data.symbol.present ? data.symbol.value : this.symbol,
      timeframe: data.timeframe.present ? data.timeframe.value : this.timeframe,
      openTime: data.openTime.present ? data.openTime.value : this.openTime,
      open: data.open.present ? data.open.value : this.open,
      high: data.high.present ? data.high.value : this.high,
      low: data.low.present ? data.low.value : this.low,
      close: data.close.present ? data.close.value : this.close,
      volume: data.volume.present ? data.volume.value : this.volume,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedCandleRow(')
          ..write('id: $id, ')
          ..write('symbol: $symbol, ')
          ..write('timeframe: $timeframe, ')
          ..write('openTime: $openTime, ')
          ..write('open: $open, ')
          ..write('high: $high, ')
          ..write('low: $low, ')
          ..write('close: $close, ')
          ..write('volume: $volume')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
      id, symbol, timeframe, openTime, open, high, low, close, volume);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedCandleRow &&
          other.id == this.id &&
          other.symbol == this.symbol &&
          other.timeframe == this.timeframe &&
          other.openTime == this.openTime &&
          other.open == this.open &&
          other.high == this.high &&
          other.low == this.low &&
          other.close == this.close &&
          other.volume == this.volume);
}

class CachedCandlesCompanion extends UpdateCompanion<CachedCandleRow> {
  final Value<int> id;
  final Value<String> symbol;
  final Value<String> timeframe;
  final Value<int> openTime;
  final Value<double> open;
  final Value<double> high;
  final Value<double> low;
  final Value<double> close;
  final Value<double> volume;
  const CachedCandlesCompanion({
    this.id = const Value.absent(),
    this.symbol = const Value.absent(),
    this.timeframe = const Value.absent(),
    this.openTime = const Value.absent(),
    this.open = const Value.absent(),
    this.high = const Value.absent(),
    this.low = const Value.absent(),
    this.close = const Value.absent(),
    this.volume = const Value.absent(),
  });
  CachedCandlesCompanion.insert({
    this.id = const Value.absent(),
    required String symbol,
    required String timeframe,
    required int openTime,
    required double open,
    required double high,
    required double low,
    required double close,
    required double volume,
  })  : symbol = Value(symbol),
        timeframe = Value(timeframe),
        openTime = Value(openTime),
        open = Value(open),
        high = Value(high),
        low = Value(low),
        close = Value(close),
        volume = Value(volume);
  static Insertable<CachedCandleRow> custom({
    Expression<int>? id,
    Expression<String>? symbol,
    Expression<String>? timeframe,
    Expression<int>? openTime,
    Expression<double>? open,
    Expression<double>? high,
    Expression<double>? low,
    Expression<double>? close,
    Expression<double>? volume,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (symbol != null) 'symbol': symbol,
      if (timeframe != null) 'timeframe': timeframe,
      if (openTime != null) 'open_time': openTime,
      if (open != null) 'open': open,
      if (high != null) 'high': high,
      if (low != null) 'low': low,
      if (close != null) 'close': close,
      if (volume != null) 'volume': volume,
    });
  }

  CachedCandlesCompanion copyWith(
      {Value<int>? id,
      Value<String>? symbol,
      Value<String>? timeframe,
      Value<int>? openTime,
      Value<double>? open,
      Value<double>? high,
      Value<double>? low,
      Value<double>? close,
      Value<double>? volume}) {
    return CachedCandlesCompanion(
      id: id ?? this.id,
      symbol: symbol ?? this.symbol,
      timeframe: timeframe ?? this.timeframe,
      openTime: openTime ?? this.openTime,
      open: open ?? this.open,
      high: high ?? this.high,
      low: low ?? this.low,
      close: close ?? this.close,
      volume: volume ?? this.volume,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (symbol.present) {
      map['symbol'] = Variable<String>(symbol.value);
    }
    if (timeframe.present) {
      map['timeframe'] = Variable<String>(timeframe.value);
    }
    if (openTime.present) {
      map['open_time'] = Variable<int>(openTime.value);
    }
    if (open.present) {
      map['open'] = Variable<double>(open.value);
    }
    if (high.present) {
      map['high'] = Variable<double>(high.value);
    }
    if (low.present) {
      map['low'] = Variable<double>(low.value);
    }
    if (close.present) {
      map['close'] = Variable<double>(close.value);
    }
    if (volume.present) {
      map['volume'] = Variable<double>(volume.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedCandlesCompanion(')
          ..write('id: $id, ')
          ..write('symbol: $symbol, ')
          ..write('timeframe: $timeframe, ')
          ..write('openTime: $openTime, ')
          ..write('open: $open, ')
          ..write('high: $high, ')
          ..write('low: $low, ')
          ..write('close: $close, ')
          ..write('volume: $volume')
          ..write(')'))
        .toString();
  }
}

class $CacheMetaTable extends CacheMeta
    with TableInfo<$CacheMetaTable, CacheMetaRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CacheMetaTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _keyMeta = const VerificationMeta('key');
  @override
  late final GeneratedColumn<String> key = GeneratedColumn<String>(
      'key', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _updatedAtMeta =
      const VerificationMeta('updatedAt');
  @override
  late final GeneratedColumn<int> updatedAt = GeneratedColumn<int>(
      'updated_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns => [key, updatedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cache_meta';
  @override
  VerificationContext validateIntegrity(Insertable<CacheMetaRow> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('key')) {
      context.handle(
          _keyMeta, key.isAcceptableOrUnknown(data['key']!, _keyMeta));
    } else if (isInserting) {
      context.missing(_keyMeta);
    }
    if (data.containsKey('updated_at')) {
      context.handle(_updatedAtMeta,
          updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta));
    } else if (isInserting) {
      context.missing(_updatedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {key};
  @override
  CacheMetaRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CacheMetaRow(
      key: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}key'])!,
      updatedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}updated_at'])!,
    );
  }

  @override
  $CacheMetaTable createAlias(String alias) {
    return $CacheMetaTable(attachedDatabase, alias);
  }
}

class CacheMetaRow extends DataClass implements Insertable<CacheMetaRow> {
  final String key;

  /// ms UTC
  final int updatedAt;
  const CacheMetaRow({required this.key, required this.updatedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['key'] = Variable<String>(key);
    map['updated_at'] = Variable<int>(updatedAt);
    return map;
  }

  CacheMetaCompanion toCompanion(bool nullToAbsent) {
    return CacheMetaCompanion(
      key: Value(key),
      updatedAt: Value(updatedAt),
    );
  }

  factory CacheMetaRow.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CacheMetaRow(
      key: serializer.fromJson<String>(json['key']),
      updatedAt: serializer.fromJson<int>(json['updatedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'key': serializer.toJson<String>(key),
      'updatedAt': serializer.toJson<int>(updatedAt),
    };
  }

  CacheMetaRow copyWith({String? key, int? updatedAt}) => CacheMetaRow(
        key: key ?? this.key,
        updatedAt: updatedAt ?? this.updatedAt,
      );
  CacheMetaRow copyWithCompanion(CacheMetaCompanion data) {
    return CacheMetaRow(
      key: data.key.present ? data.key.value : this.key,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CacheMetaRow(')
          ..write('key: $key, ')
          ..write('updatedAt: $updatedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(key, updatedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CacheMetaRow &&
          other.key == this.key &&
          other.updatedAt == this.updatedAt);
}

class CacheMetaCompanion extends UpdateCompanion<CacheMetaRow> {
  final Value<String> key;
  final Value<int> updatedAt;
  final Value<int> rowid;
  const CacheMetaCompanion({
    this.key = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CacheMetaCompanion.insert({
    required String key,
    required int updatedAt,
    this.rowid = const Value.absent(),
  })  : key = Value(key),
        updatedAt = Value(updatedAt);
  static Insertable<CacheMetaRow> custom({
    Expression<String>? key,
    Expression<int>? updatedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (key != null) 'key': key,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CacheMetaCompanion copyWith(
      {Value<String>? key, Value<int>? updatedAt, Value<int>? rowid}) {
    return CacheMetaCompanion(
      key: key ?? this.key,
      updatedAt: updatedAt ?? this.updatedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (key.present) {
      map['key'] = Variable<String>(key.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<int>(updatedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CacheMetaCompanion(')
          ..write('key: $key, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CachedSignalsTable extends CachedSignals
    with TableInfo<$CachedSignalsTable, CachedSignalRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedSignalsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _scopeMeta = const VerificationMeta('scope');
  @override
  late final GeneratedColumn<String> scope = GeneratedColumn<String>(
      'scope', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _ownerMeta = const VerificationMeta('owner');
  @override
  late final GeneratedColumn<String> owner = GeneratedColumn<String>(
      'owner', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _positionMeta =
      const VerificationMeta('position');
  @override
  late final GeneratedColumn<int> position = GeneratedColumn<int>(
      'position', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _payloadMeta =
      const VerificationMeta('payload');
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
      'payload', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _savedAtMeta =
      const VerificationMeta('savedAt');
  @override
  late final GeneratedColumn<int> savedAt = GeneratedColumn<int>(
      'saved_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _validUntilMeta =
      const VerificationMeta('validUntil');
  @override
  late final GeneratedColumn<int> validUntil = GeneratedColumn<int>(
      'valid_until', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns =>
      [scope, owner, id, position, payload, savedAt, validUntil];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_signals';
  @override
  VerificationContext validateIntegrity(Insertable<CachedSignalRow> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('scope')) {
      context.handle(
          _scopeMeta, scope.isAcceptableOrUnknown(data['scope']!, _scopeMeta));
    } else if (isInserting) {
      context.missing(_scopeMeta);
    }
    if (data.containsKey('owner')) {
      context.handle(
          _ownerMeta, owner.isAcceptableOrUnknown(data['owner']!, _ownerMeta));
    } else if (isInserting) {
      context.missing(_ownerMeta);
    }
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('position')) {
      context.handle(_positionMeta,
          position.isAcceptableOrUnknown(data['position']!, _positionMeta));
    } else if (isInserting) {
      context.missing(_positionMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(_payloadMeta,
          payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta));
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('saved_at')) {
      context.handle(_savedAtMeta,
          savedAt.isAcceptableOrUnknown(data['saved_at']!, _savedAtMeta));
    } else if (isInserting) {
      context.missing(_savedAtMeta);
    }
    if (data.containsKey('valid_until')) {
      context.handle(
          _validUntilMeta,
          validUntil.isAcceptableOrUnknown(
              data['valid_until']!, _validUntilMeta));
    } else if (isInserting) {
      context.missing(_validUntilMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {scope, owner, id};
  @override
  CachedSignalRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedSignalRow(
      scope: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}scope'])!,
      owner: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}owner'])!,
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      position: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}position'])!,
      payload: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}payload'])!,
      savedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}saved_at'])!,
      validUntil: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}valid_until'])!,
    );
  }

  @override
  $CachedSignalsTable createAlias(String alias) {
    return $CachedSignalsTable(attachedDatabase, alias);
  }
}

class CachedSignalRow extends DataClass implements Insertable<CachedSignalRow> {
  final String scope;
  final String owner;
  final String id;

  /// الترتيب جوّا القائمة
  final int position;
  final String payload;

  /// ms UTC
  final int savedAt;

  /// صلاحية الإشارة (ms UTC) - التقليم بيشيل يلي خلصت من زمان
  final int validUntil;
  const CachedSignalRow(
      {required this.scope,
      required this.owner,
      required this.id,
      required this.position,
      required this.payload,
      required this.savedAt,
      required this.validUntil});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['scope'] = Variable<String>(scope);
    map['owner'] = Variable<String>(owner);
    map['id'] = Variable<String>(id);
    map['position'] = Variable<int>(position);
    map['payload'] = Variable<String>(payload);
    map['saved_at'] = Variable<int>(savedAt);
    map['valid_until'] = Variable<int>(validUntil);
    return map;
  }

  CachedSignalsCompanion toCompanion(bool nullToAbsent) {
    return CachedSignalsCompanion(
      scope: Value(scope),
      owner: Value(owner),
      id: Value(id),
      position: Value(position),
      payload: Value(payload),
      savedAt: Value(savedAt),
      validUntil: Value(validUntil),
    );
  }

  factory CachedSignalRow.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedSignalRow(
      scope: serializer.fromJson<String>(json['scope']),
      owner: serializer.fromJson<String>(json['owner']),
      id: serializer.fromJson<String>(json['id']),
      position: serializer.fromJson<int>(json['position']),
      payload: serializer.fromJson<String>(json['payload']),
      savedAt: serializer.fromJson<int>(json['savedAt']),
      validUntil: serializer.fromJson<int>(json['validUntil']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'scope': serializer.toJson<String>(scope),
      'owner': serializer.toJson<String>(owner),
      'id': serializer.toJson<String>(id),
      'position': serializer.toJson<int>(position),
      'payload': serializer.toJson<String>(payload),
      'savedAt': serializer.toJson<int>(savedAt),
      'validUntil': serializer.toJson<int>(validUntil),
    };
  }

  CachedSignalRow copyWith(
          {String? scope,
          String? owner,
          String? id,
          int? position,
          String? payload,
          int? savedAt,
          int? validUntil}) =>
      CachedSignalRow(
        scope: scope ?? this.scope,
        owner: owner ?? this.owner,
        id: id ?? this.id,
        position: position ?? this.position,
        payload: payload ?? this.payload,
        savedAt: savedAt ?? this.savedAt,
        validUntil: validUntil ?? this.validUntil,
      );
  CachedSignalRow copyWithCompanion(CachedSignalsCompanion data) {
    return CachedSignalRow(
      scope: data.scope.present ? data.scope.value : this.scope,
      owner: data.owner.present ? data.owner.value : this.owner,
      id: data.id.present ? data.id.value : this.id,
      position: data.position.present ? data.position.value : this.position,
      payload: data.payload.present ? data.payload.value : this.payload,
      savedAt: data.savedAt.present ? data.savedAt.value : this.savedAt,
      validUntil:
          data.validUntil.present ? data.validUntil.value : this.validUntil,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedSignalRow(')
          ..write('scope: $scope, ')
          ..write('owner: $owner, ')
          ..write('id: $id, ')
          ..write('position: $position, ')
          ..write('payload: $payload, ')
          ..write('savedAt: $savedAt, ')
          ..write('validUntil: $validUntil')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(scope, owner, id, position, payload, savedAt, validUntil);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedSignalRow &&
          other.scope == this.scope &&
          other.owner == this.owner &&
          other.id == this.id &&
          other.position == this.position &&
          other.payload == this.payload &&
          other.savedAt == this.savedAt &&
          other.validUntil == this.validUntil);
}

class CachedSignalsCompanion extends UpdateCompanion<CachedSignalRow> {
  final Value<String> scope;
  final Value<String> owner;
  final Value<String> id;
  final Value<int> position;
  final Value<String> payload;
  final Value<int> savedAt;
  final Value<int> validUntil;
  final Value<int> rowid;
  const CachedSignalsCompanion({
    this.scope = const Value.absent(),
    this.owner = const Value.absent(),
    this.id = const Value.absent(),
    this.position = const Value.absent(),
    this.payload = const Value.absent(),
    this.savedAt = const Value.absent(),
    this.validUntil = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CachedSignalsCompanion.insert({
    required String scope,
    required String owner,
    required String id,
    required int position,
    required String payload,
    required int savedAt,
    required int validUntil,
    this.rowid = const Value.absent(),
  })  : scope = Value(scope),
        owner = Value(owner),
        id = Value(id),
        position = Value(position),
        payload = Value(payload),
        savedAt = Value(savedAt),
        validUntil = Value(validUntil);
  static Insertable<CachedSignalRow> custom({
    Expression<String>? scope,
    Expression<String>? owner,
    Expression<String>? id,
    Expression<int>? position,
    Expression<String>? payload,
    Expression<int>? savedAt,
    Expression<int>? validUntil,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (scope != null) 'scope': scope,
      if (owner != null) 'owner': owner,
      if (id != null) 'id': id,
      if (position != null) 'position': position,
      if (payload != null) 'payload': payload,
      if (savedAt != null) 'saved_at': savedAt,
      if (validUntil != null) 'valid_until': validUntil,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CachedSignalsCompanion copyWith(
      {Value<String>? scope,
      Value<String>? owner,
      Value<String>? id,
      Value<int>? position,
      Value<String>? payload,
      Value<int>? savedAt,
      Value<int>? validUntil,
      Value<int>? rowid}) {
    return CachedSignalsCompanion(
      scope: scope ?? this.scope,
      owner: owner ?? this.owner,
      id: id ?? this.id,
      position: position ?? this.position,
      payload: payload ?? this.payload,
      savedAt: savedAt ?? this.savedAt,
      validUntil: validUntil ?? this.validUntil,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (scope.present) {
      map['scope'] = Variable<String>(scope.value);
    }
    if (owner.present) {
      map['owner'] = Variable<String>(owner.value);
    }
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (position.present) {
      map['position'] = Variable<int>(position.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (savedAt.present) {
      map['saved_at'] = Variable<int>(savedAt.value);
    }
    if (validUntil.present) {
      map['valid_until'] = Variable<int>(validUntil.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedSignalsCompanion(')
          ..write('scope: $scope, ')
          ..write('owner: $owner, ')
          ..write('id: $id, ')
          ..write('position: $position, ')
          ..write('payload: $payload, ')
          ..write('savedAt: $savedAt, ')
          ..write('validUntil: $validUntil, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CachedNewsTable extends CachedNews
    with TableInfo<$CachedNewsTable, CachedNewsRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedNewsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _languageMeta =
      const VerificationMeta('language');
  @override
  late final GeneratedColumn<String> language = GeneratedColumn<String>(
      'language', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _kindMeta = const VerificationMeta('kind');
  @override
  late final GeneratedColumn<String> kind = GeneratedColumn<String>(
      'kind', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _positionMeta =
      const VerificationMeta('position');
  @override
  late final GeneratedColumn<int> position = GeneratedColumn<int>(
      'position', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _payloadMeta =
      const VerificationMeta('payload');
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
      'payload', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _savedAtMeta =
      const VerificationMeta('savedAt');
  @override
  late final GeneratedColumn<int> savedAt = GeneratedColumn<int>(
      'saved_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns =>
      [language, kind, id, position, payload, savedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_news';
  @override
  VerificationContext validateIntegrity(Insertable<CachedNewsRow> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('language')) {
      context.handle(_languageMeta,
          language.isAcceptableOrUnknown(data['language']!, _languageMeta));
    } else if (isInserting) {
      context.missing(_languageMeta);
    }
    if (data.containsKey('kind')) {
      context.handle(
          _kindMeta, kind.isAcceptableOrUnknown(data['kind']!, _kindMeta));
    } else if (isInserting) {
      context.missing(_kindMeta);
    }
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('position')) {
      context.handle(_positionMeta,
          position.isAcceptableOrUnknown(data['position']!, _positionMeta));
    } else if (isInserting) {
      context.missing(_positionMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(_payloadMeta,
          payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta));
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('saved_at')) {
      context.handle(_savedAtMeta,
          savedAt.isAcceptableOrUnknown(data['saved_at']!, _savedAtMeta));
    } else if (isInserting) {
      context.missing(_savedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {language, kind, id};
  @override
  CachedNewsRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedNewsRow(
      language: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}language'])!,
      kind: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}kind'])!,
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      position: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}position'])!,
      payload: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}payload'])!,
      savedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}saved_at'])!,
    );
  }

  @override
  $CachedNewsTable createAlias(String alias) {
    return $CachedNewsTable(attachedDatabase, alias);
  }
}

class CachedNewsRow extends DataClass implements Insertable<CachedNewsRow> {
  final String language;
  final String kind;
  final String id;
  final int position;
  final String payload;

  /// ms UTC
  final int savedAt;
  const CachedNewsRow(
      {required this.language,
      required this.kind,
      required this.id,
      required this.position,
      required this.payload,
      required this.savedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['language'] = Variable<String>(language);
    map['kind'] = Variable<String>(kind);
    map['id'] = Variable<String>(id);
    map['position'] = Variable<int>(position);
    map['payload'] = Variable<String>(payload);
    map['saved_at'] = Variable<int>(savedAt);
    return map;
  }

  CachedNewsCompanion toCompanion(bool nullToAbsent) {
    return CachedNewsCompanion(
      language: Value(language),
      kind: Value(kind),
      id: Value(id),
      position: Value(position),
      payload: Value(payload),
      savedAt: Value(savedAt),
    );
  }

  factory CachedNewsRow.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedNewsRow(
      language: serializer.fromJson<String>(json['language']),
      kind: serializer.fromJson<String>(json['kind']),
      id: serializer.fromJson<String>(json['id']),
      position: serializer.fromJson<int>(json['position']),
      payload: serializer.fromJson<String>(json['payload']),
      savedAt: serializer.fromJson<int>(json['savedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'language': serializer.toJson<String>(language),
      'kind': serializer.toJson<String>(kind),
      'id': serializer.toJson<String>(id),
      'position': serializer.toJson<int>(position),
      'payload': serializer.toJson<String>(payload),
      'savedAt': serializer.toJson<int>(savedAt),
    };
  }

  CachedNewsRow copyWith(
          {String? language,
          String? kind,
          String? id,
          int? position,
          String? payload,
          int? savedAt}) =>
      CachedNewsRow(
        language: language ?? this.language,
        kind: kind ?? this.kind,
        id: id ?? this.id,
        position: position ?? this.position,
        payload: payload ?? this.payload,
        savedAt: savedAt ?? this.savedAt,
      );
  CachedNewsRow copyWithCompanion(CachedNewsCompanion data) {
    return CachedNewsRow(
      language: data.language.present ? data.language.value : this.language,
      kind: data.kind.present ? data.kind.value : this.kind,
      id: data.id.present ? data.id.value : this.id,
      position: data.position.present ? data.position.value : this.position,
      payload: data.payload.present ? data.payload.value : this.payload,
      savedAt: data.savedAt.present ? data.savedAt.value : this.savedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedNewsRow(')
          ..write('language: $language, ')
          ..write('kind: $kind, ')
          ..write('id: $id, ')
          ..write('position: $position, ')
          ..write('payload: $payload, ')
          ..write('savedAt: $savedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(language, kind, id, position, payload, savedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedNewsRow &&
          other.language == this.language &&
          other.kind == this.kind &&
          other.id == this.id &&
          other.position == this.position &&
          other.payload == this.payload &&
          other.savedAt == this.savedAt);
}

class CachedNewsCompanion extends UpdateCompanion<CachedNewsRow> {
  final Value<String> language;
  final Value<String> kind;
  final Value<String> id;
  final Value<int> position;
  final Value<String> payload;
  final Value<int> savedAt;
  final Value<int> rowid;
  const CachedNewsCompanion({
    this.language = const Value.absent(),
    this.kind = const Value.absent(),
    this.id = const Value.absent(),
    this.position = const Value.absent(),
    this.payload = const Value.absent(),
    this.savedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CachedNewsCompanion.insert({
    required String language,
    required String kind,
    required String id,
    required int position,
    required String payload,
    required int savedAt,
    this.rowid = const Value.absent(),
  })  : language = Value(language),
        kind = Value(kind),
        id = Value(id),
        position = Value(position),
        payload = Value(payload),
        savedAt = Value(savedAt);
  static Insertable<CachedNewsRow> custom({
    Expression<String>? language,
    Expression<String>? kind,
    Expression<String>? id,
    Expression<int>? position,
    Expression<String>? payload,
    Expression<int>? savedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (language != null) 'language': language,
      if (kind != null) 'kind': kind,
      if (id != null) 'id': id,
      if (position != null) 'position': position,
      if (payload != null) 'payload': payload,
      if (savedAt != null) 'saved_at': savedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CachedNewsCompanion copyWith(
      {Value<String>? language,
      Value<String>? kind,
      Value<String>? id,
      Value<int>? position,
      Value<String>? payload,
      Value<int>? savedAt,
      Value<int>? rowid}) {
    return CachedNewsCompanion(
      language: language ?? this.language,
      kind: kind ?? this.kind,
      id: id ?? this.id,
      position: position ?? this.position,
      payload: payload ?? this.payload,
      savedAt: savedAt ?? this.savedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (language.present) {
      map['language'] = Variable<String>(language.value);
    }
    if (kind.present) {
      map['kind'] = Variable<String>(kind.value);
    }
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (position.present) {
      map['position'] = Variable<int>(position.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (savedAt.present) {
      map['saved_at'] = Variable<int>(savedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedNewsCompanion(')
          ..write('language: $language, ')
          ..write('kind: $kind, ')
          ..write('id: $id, ')
          ..write('position: $position, ')
          ..write('payload: $payload, ')
          ..write('savedAt: $savedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CachedNotificationsTable extends CachedNotifications
    with TableInfo<$CachedNotificationsTable, CachedNotificationRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CachedNotificationsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _ownerMeta = const VerificationMeta('owner');
  @override
  late final GeneratedColumn<String> owner = GeneratedColumn<String>(
      'owner', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _languageMeta =
      const VerificationMeta('language');
  @override
  late final GeneratedColumn<String> language = GeneratedColumn<String>(
      'language', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
      'id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _positionMeta =
      const VerificationMeta('position');
  @override
  late final GeneratedColumn<int> position = GeneratedColumn<int>(
      'position', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _payloadMeta =
      const VerificationMeta('payload');
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
      'payload', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _savedAtMeta =
      const VerificationMeta('savedAt');
  @override
  late final GeneratedColumn<int> savedAt = GeneratedColumn<int>(
      'saved_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns =>
      [owner, language, id, position, payload, savedAt];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'cached_notifications';
  @override
  VerificationContext validateIntegrity(
      Insertable<CachedNotificationRow> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('owner')) {
      context.handle(
          _ownerMeta, owner.isAcceptableOrUnknown(data['owner']!, _ownerMeta));
    } else if (isInserting) {
      context.missing(_ownerMeta);
    }
    if (data.containsKey('language')) {
      context.handle(_languageMeta,
          language.isAcceptableOrUnknown(data['language']!, _languageMeta));
    } else if (isInserting) {
      context.missing(_languageMeta);
    }
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('position')) {
      context.handle(_positionMeta,
          position.isAcceptableOrUnknown(data['position']!, _positionMeta));
    } else if (isInserting) {
      context.missing(_positionMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(_payloadMeta,
          payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta));
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('saved_at')) {
      context.handle(_savedAtMeta,
          savedAt.isAcceptableOrUnknown(data['saved_at']!, _savedAtMeta));
    } else if (isInserting) {
      context.missing(_savedAtMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {owner, language, id};
  @override
  CachedNotificationRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CachedNotificationRow(
      owner: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}owner'])!,
      language: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}language'])!,
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}id'])!,
      position: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}position'])!,
      payload: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}payload'])!,
      savedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}saved_at'])!,
    );
  }

  @override
  $CachedNotificationsTable createAlias(String alias) {
    return $CachedNotificationsTable(attachedDatabase, alias);
  }
}

class CachedNotificationRow extends DataClass
    implements Insertable<CachedNotificationRow> {
  final String owner;
  final String language;
  final String id;
  final int position;
  final String payload;

  /// ms UTC
  final int savedAt;
  const CachedNotificationRow(
      {required this.owner,
      required this.language,
      required this.id,
      required this.position,
      required this.payload,
      required this.savedAt});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['owner'] = Variable<String>(owner);
    map['language'] = Variable<String>(language);
    map['id'] = Variable<String>(id);
    map['position'] = Variable<int>(position);
    map['payload'] = Variable<String>(payload);
    map['saved_at'] = Variable<int>(savedAt);
    return map;
  }

  CachedNotificationsCompanion toCompanion(bool nullToAbsent) {
    return CachedNotificationsCompanion(
      owner: Value(owner),
      language: Value(language),
      id: Value(id),
      position: Value(position),
      payload: Value(payload),
      savedAt: Value(savedAt),
    );
  }

  factory CachedNotificationRow.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CachedNotificationRow(
      owner: serializer.fromJson<String>(json['owner']),
      language: serializer.fromJson<String>(json['language']),
      id: serializer.fromJson<String>(json['id']),
      position: serializer.fromJson<int>(json['position']),
      payload: serializer.fromJson<String>(json['payload']),
      savedAt: serializer.fromJson<int>(json['savedAt']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'owner': serializer.toJson<String>(owner),
      'language': serializer.toJson<String>(language),
      'id': serializer.toJson<String>(id),
      'position': serializer.toJson<int>(position),
      'payload': serializer.toJson<String>(payload),
      'savedAt': serializer.toJson<int>(savedAt),
    };
  }

  CachedNotificationRow copyWith(
          {String? owner,
          String? language,
          String? id,
          int? position,
          String? payload,
          int? savedAt}) =>
      CachedNotificationRow(
        owner: owner ?? this.owner,
        language: language ?? this.language,
        id: id ?? this.id,
        position: position ?? this.position,
        payload: payload ?? this.payload,
        savedAt: savedAt ?? this.savedAt,
      );
  CachedNotificationRow copyWithCompanion(CachedNotificationsCompanion data) {
    return CachedNotificationRow(
      owner: data.owner.present ? data.owner.value : this.owner,
      language: data.language.present ? data.language.value : this.language,
      id: data.id.present ? data.id.value : this.id,
      position: data.position.present ? data.position.value : this.position,
      payload: data.payload.present ? data.payload.value : this.payload,
      savedAt: data.savedAt.present ? data.savedAt.value : this.savedAt,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CachedNotificationRow(')
          ..write('owner: $owner, ')
          ..write('language: $language, ')
          ..write('id: $id, ')
          ..write('position: $position, ')
          ..write('payload: $payload, ')
          ..write('savedAt: $savedAt')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(owner, language, id, position, payload, savedAt);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CachedNotificationRow &&
          other.owner == this.owner &&
          other.language == this.language &&
          other.id == this.id &&
          other.position == this.position &&
          other.payload == this.payload &&
          other.savedAt == this.savedAt);
}

class CachedNotificationsCompanion
    extends UpdateCompanion<CachedNotificationRow> {
  final Value<String> owner;
  final Value<String> language;
  final Value<String> id;
  final Value<int> position;
  final Value<String> payload;
  final Value<int> savedAt;
  final Value<int> rowid;
  const CachedNotificationsCompanion({
    this.owner = const Value.absent(),
    this.language = const Value.absent(),
    this.id = const Value.absent(),
    this.position = const Value.absent(),
    this.payload = const Value.absent(),
    this.savedAt = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CachedNotificationsCompanion.insert({
    required String owner,
    required String language,
    required String id,
    required int position,
    required String payload,
    required int savedAt,
    this.rowid = const Value.absent(),
  })  : owner = Value(owner),
        language = Value(language),
        id = Value(id),
        position = Value(position),
        payload = Value(payload),
        savedAt = Value(savedAt);
  static Insertable<CachedNotificationRow> custom({
    Expression<String>? owner,
    Expression<String>? language,
    Expression<String>? id,
    Expression<int>? position,
    Expression<String>? payload,
    Expression<int>? savedAt,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (owner != null) 'owner': owner,
      if (language != null) 'language': language,
      if (id != null) 'id': id,
      if (position != null) 'position': position,
      if (payload != null) 'payload': payload,
      if (savedAt != null) 'saved_at': savedAt,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CachedNotificationsCompanion copyWith(
      {Value<String>? owner,
      Value<String>? language,
      Value<String>? id,
      Value<int>? position,
      Value<String>? payload,
      Value<int>? savedAt,
      Value<int>? rowid}) {
    return CachedNotificationsCompanion(
      owner: owner ?? this.owner,
      language: language ?? this.language,
      id: id ?? this.id,
      position: position ?? this.position,
      payload: payload ?? this.payload,
      savedAt: savedAt ?? this.savedAt,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (owner.present) {
      map['owner'] = Variable<String>(owner.value);
    }
    if (language.present) {
      map['language'] = Variable<String>(language.value);
    }
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (position.present) {
      map['position'] = Variable<int>(position.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (savedAt.present) {
      map['saved_at'] = Variable<int>(savedAt.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CachedNotificationsCompanion(')
          ..write('owner: $owner, ')
          ..write('language: $language, ')
          ..write('id: $id, ')
          ..write('position: $position, ')
          ..write('payload: $payload, ')
          ..write('savedAt: $savedAt, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $CachedQuotesTable cachedQuotes = $CachedQuotesTable(this);
  late final $CachedCandlesTable cachedCandles = $CachedCandlesTable(this);
  late final $CacheMetaTable cacheMeta = $CacheMetaTable(this);
  late final $CachedSignalsTable cachedSignals = $CachedSignalsTable(this);
  late final $CachedNewsTable cachedNews = $CachedNewsTable(this);
  late final $CachedNotificationsTable cachedNotifications =
      $CachedNotificationsTable(this);
  late final Index idxCachedCandlesSeries = Index('idx_cached_candles_series',
      'CREATE UNIQUE INDEX idx_cached_candles_series ON cached_candles (symbol, timeframe, open_time)');
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
        cachedQuotes,
        cachedCandles,
        cacheMeta,
        cachedSignals,
        cachedNews,
        cachedNotifications,
        idxCachedCandlesSeries
      ];
}

typedef $$CachedQuotesTableCreateCompanionBuilder = CachedQuotesCompanion
    Function({
  required String symbol,
  required double price,
  required double change,
  required int updatedAt,
  Value<int> rowid,
});
typedef $$CachedQuotesTableUpdateCompanionBuilder = CachedQuotesCompanion
    Function({
  Value<String> symbol,
  Value<double> price,
  Value<double> change,
  Value<int> updatedAt,
  Value<int> rowid,
});

class $$CachedQuotesTableFilterComposer
    extends Composer<_$AppDatabase, $CachedQuotesTable> {
  $$CachedQuotesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get symbol => $composableBuilder(
      column: $table.symbol, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get price => $composableBuilder(
      column: $table.price, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get change => $composableBuilder(
      column: $table.change, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get updatedAt => $composableBuilder(
      column: $table.updatedAt, builder: (column) => ColumnFilters(column));
}

class $$CachedQuotesTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedQuotesTable> {
  $$CachedQuotesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get symbol => $composableBuilder(
      column: $table.symbol, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get price => $composableBuilder(
      column: $table.price, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get change => $composableBuilder(
      column: $table.change, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get updatedAt => $composableBuilder(
      column: $table.updatedAt, builder: (column) => ColumnOrderings(column));
}

class $$CachedQuotesTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedQuotesTable> {
  $$CachedQuotesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get symbol =>
      $composableBuilder(column: $table.symbol, builder: (column) => column);

  GeneratedColumn<double> get price =>
      $composableBuilder(column: $table.price, builder: (column) => column);

  GeneratedColumn<double> get change =>
      $composableBuilder(column: $table.change, builder: (column) => column);

  GeneratedColumn<int> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);
}

class $$CachedQuotesTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CachedQuotesTable,
    CachedQuoteRow,
    $$CachedQuotesTableFilterComposer,
    $$CachedQuotesTableOrderingComposer,
    $$CachedQuotesTableAnnotationComposer,
    $$CachedQuotesTableCreateCompanionBuilder,
    $$CachedQuotesTableUpdateCompanionBuilder,
    (
      CachedQuoteRow,
      BaseReferences<_$AppDatabase, $CachedQuotesTable, CachedQuoteRow>
    ),
    CachedQuoteRow,
    PrefetchHooks Function()> {
  $$CachedQuotesTableTableManager(_$AppDatabase db, $CachedQuotesTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CachedQuotesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CachedQuotesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CachedQuotesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> symbol = const Value.absent(),
            Value<double> price = const Value.absent(),
            Value<double> change = const Value.absent(),
            Value<int> updatedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedQuotesCompanion(
            symbol: symbol,
            price: price,
            change: change,
            updatedAt: updatedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String symbol,
            required double price,
            required double change,
            required int updatedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedQuotesCompanion.insert(
            symbol: symbol,
            price: price,
            change: change,
            updatedAt: updatedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$CachedQuotesTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CachedQuotesTable,
    CachedQuoteRow,
    $$CachedQuotesTableFilterComposer,
    $$CachedQuotesTableOrderingComposer,
    $$CachedQuotesTableAnnotationComposer,
    $$CachedQuotesTableCreateCompanionBuilder,
    $$CachedQuotesTableUpdateCompanionBuilder,
    (
      CachedQuoteRow,
      BaseReferences<_$AppDatabase, $CachedQuotesTable, CachedQuoteRow>
    ),
    CachedQuoteRow,
    PrefetchHooks Function()>;
typedef $$CachedCandlesTableCreateCompanionBuilder = CachedCandlesCompanion
    Function({
  Value<int> id,
  required String symbol,
  required String timeframe,
  required int openTime,
  required double open,
  required double high,
  required double low,
  required double close,
  required double volume,
});
typedef $$CachedCandlesTableUpdateCompanionBuilder = CachedCandlesCompanion
    Function({
  Value<int> id,
  Value<String> symbol,
  Value<String> timeframe,
  Value<int> openTime,
  Value<double> open,
  Value<double> high,
  Value<double> low,
  Value<double> close,
  Value<double> volume,
});

class $$CachedCandlesTableFilterComposer
    extends Composer<_$AppDatabase, $CachedCandlesTable> {
  $$CachedCandlesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get symbol => $composableBuilder(
      column: $table.symbol, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get timeframe => $composableBuilder(
      column: $table.timeframe, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get openTime => $composableBuilder(
      column: $table.openTime, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get open => $composableBuilder(
      column: $table.open, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get high => $composableBuilder(
      column: $table.high, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get low => $composableBuilder(
      column: $table.low, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get close => $composableBuilder(
      column: $table.close, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get volume => $composableBuilder(
      column: $table.volume, builder: (column) => ColumnFilters(column));
}

class $$CachedCandlesTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedCandlesTable> {
  $$CachedCandlesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get symbol => $composableBuilder(
      column: $table.symbol, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get timeframe => $composableBuilder(
      column: $table.timeframe, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get openTime => $composableBuilder(
      column: $table.openTime, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get open => $composableBuilder(
      column: $table.open, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get high => $composableBuilder(
      column: $table.high, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get low => $composableBuilder(
      column: $table.low, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get close => $composableBuilder(
      column: $table.close, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get volume => $composableBuilder(
      column: $table.volume, builder: (column) => ColumnOrderings(column));
}

class $$CachedCandlesTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedCandlesTable> {
  $$CachedCandlesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get symbol =>
      $composableBuilder(column: $table.symbol, builder: (column) => column);

  GeneratedColumn<String> get timeframe =>
      $composableBuilder(column: $table.timeframe, builder: (column) => column);

  GeneratedColumn<int> get openTime =>
      $composableBuilder(column: $table.openTime, builder: (column) => column);

  GeneratedColumn<double> get open =>
      $composableBuilder(column: $table.open, builder: (column) => column);

  GeneratedColumn<double> get high =>
      $composableBuilder(column: $table.high, builder: (column) => column);

  GeneratedColumn<double> get low =>
      $composableBuilder(column: $table.low, builder: (column) => column);

  GeneratedColumn<double> get close =>
      $composableBuilder(column: $table.close, builder: (column) => column);

  GeneratedColumn<double> get volume =>
      $composableBuilder(column: $table.volume, builder: (column) => column);
}

class $$CachedCandlesTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CachedCandlesTable,
    CachedCandleRow,
    $$CachedCandlesTableFilterComposer,
    $$CachedCandlesTableOrderingComposer,
    $$CachedCandlesTableAnnotationComposer,
    $$CachedCandlesTableCreateCompanionBuilder,
    $$CachedCandlesTableUpdateCompanionBuilder,
    (
      CachedCandleRow,
      BaseReferences<_$AppDatabase, $CachedCandlesTable, CachedCandleRow>
    ),
    CachedCandleRow,
    PrefetchHooks Function()> {
  $$CachedCandlesTableTableManager(_$AppDatabase db, $CachedCandlesTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CachedCandlesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CachedCandlesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CachedCandlesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> id = const Value.absent(),
            Value<String> symbol = const Value.absent(),
            Value<String> timeframe = const Value.absent(),
            Value<int> openTime = const Value.absent(),
            Value<double> open = const Value.absent(),
            Value<double> high = const Value.absent(),
            Value<double> low = const Value.absent(),
            Value<double> close = const Value.absent(),
            Value<double> volume = const Value.absent(),
          }) =>
              CachedCandlesCompanion(
            id: id,
            symbol: symbol,
            timeframe: timeframe,
            openTime: openTime,
            open: open,
            high: high,
            low: low,
            close: close,
            volume: volume,
          ),
          createCompanionCallback: ({
            Value<int> id = const Value.absent(),
            required String symbol,
            required String timeframe,
            required int openTime,
            required double open,
            required double high,
            required double low,
            required double close,
            required double volume,
          }) =>
              CachedCandlesCompanion.insert(
            id: id,
            symbol: symbol,
            timeframe: timeframe,
            openTime: openTime,
            open: open,
            high: high,
            low: low,
            close: close,
            volume: volume,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$CachedCandlesTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CachedCandlesTable,
    CachedCandleRow,
    $$CachedCandlesTableFilterComposer,
    $$CachedCandlesTableOrderingComposer,
    $$CachedCandlesTableAnnotationComposer,
    $$CachedCandlesTableCreateCompanionBuilder,
    $$CachedCandlesTableUpdateCompanionBuilder,
    (
      CachedCandleRow,
      BaseReferences<_$AppDatabase, $CachedCandlesTable, CachedCandleRow>
    ),
    CachedCandleRow,
    PrefetchHooks Function()>;
typedef $$CacheMetaTableCreateCompanionBuilder = CacheMetaCompanion Function({
  required String key,
  required int updatedAt,
  Value<int> rowid,
});
typedef $$CacheMetaTableUpdateCompanionBuilder = CacheMetaCompanion Function({
  Value<String> key,
  Value<int> updatedAt,
  Value<int> rowid,
});

class $$CacheMetaTableFilterComposer
    extends Composer<_$AppDatabase, $CacheMetaTable> {
  $$CacheMetaTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get key => $composableBuilder(
      column: $table.key, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get updatedAt => $composableBuilder(
      column: $table.updatedAt, builder: (column) => ColumnFilters(column));
}

class $$CacheMetaTableOrderingComposer
    extends Composer<_$AppDatabase, $CacheMetaTable> {
  $$CacheMetaTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get key => $composableBuilder(
      column: $table.key, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get updatedAt => $composableBuilder(
      column: $table.updatedAt, builder: (column) => ColumnOrderings(column));
}

class $$CacheMetaTableAnnotationComposer
    extends Composer<_$AppDatabase, $CacheMetaTable> {
  $$CacheMetaTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get key =>
      $composableBuilder(column: $table.key, builder: (column) => column);

  GeneratedColumn<int> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);
}

class $$CacheMetaTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CacheMetaTable,
    CacheMetaRow,
    $$CacheMetaTableFilterComposer,
    $$CacheMetaTableOrderingComposer,
    $$CacheMetaTableAnnotationComposer,
    $$CacheMetaTableCreateCompanionBuilder,
    $$CacheMetaTableUpdateCompanionBuilder,
    (
      CacheMetaRow,
      BaseReferences<_$AppDatabase, $CacheMetaTable, CacheMetaRow>
    ),
    CacheMetaRow,
    PrefetchHooks Function()> {
  $$CacheMetaTableTableManager(_$AppDatabase db, $CacheMetaTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CacheMetaTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CacheMetaTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CacheMetaTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> key = const Value.absent(),
            Value<int> updatedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              CacheMetaCompanion(
            key: key,
            updatedAt: updatedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String key,
            required int updatedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              CacheMetaCompanion.insert(
            key: key,
            updatedAt: updatedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$CacheMetaTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CacheMetaTable,
    CacheMetaRow,
    $$CacheMetaTableFilterComposer,
    $$CacheMetaTableOrderingComposer,
    $$CacheMetaTableAnnotationComposer,
    $$CacheMetaTableCreateCompanionBuilder,
    $$CacheMetaTableUpdateCompanionBuilder,
    (
      CacheMetaRow,
      BaseReferences<_$AppDatabase, $CacheMetaTable, CacheMetaRow>
    ),
    CacheMetaRow,
    PrefetchHooks Function()>;
typedef $$CachedSignalsTableCreateCompanionBuilder = CachedSignalsCompanion
    Function({
  required String scope,
  required String owner,
  required String id,
  required int position,
  required String payload,
  required int savedAt,
  required int validUntil,
  Value<int> rowid,
});
typedef $$CachedSignalsTableUpdateCompanionBuilder = CachedSignalsCompanion
    Function({
  Value<String> scope,
  Value<String> owner,
  Value<String> id,
  Value<int> position,
  Value<String> payload,
  Value<int> savedAt,
  Value<int> validUntil,
  Value<int> rowid,
});

class $$CachedSignalsTableFilterComposer
    extends Composer<_$AppDatabase, $CachedSignalsTable> {
  $$CachedSignalsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get scope => $composableBuilder(
      column: $table.scope, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get owner => $composableBuilder(
      column: $table.owner, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get position => $composableBuilder(
      column: $table.position, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get payload => $composableBuilder(
      column: $table.payload, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get savedAt => $composableBuilder(
      column: $table.savedAt, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get validUntil => $composableBuilder(
      column: $table.validUntil, builder: (column) => ColumnFilters(column));
}

class $$CachedSignalsTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedSignalsTable> {
  $$CachedSignalsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get scope => $composableBuilder(
      column: $table.scope, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get owner => $composableBuilder(
      column: $table.owner, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get position => $composableBuilder(
      column: $table.position, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get payload => $composableBuilder(
      column: $table.payload, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get savedAt => $composableBuilder(
      column: $table.savedAt, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get validUntil => $composableBuilder(
      column: $table.validUntil, builder: (column) => ColumnOrderings(column));
}

class $$CachedSignalsTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedSignalsTable> {
  $$CachedSignalsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get scope =>
      $composableBuilder(column: $table.scope, builder: (column) => column);

  GeneratedColumn<String> get owner =>
      $composableBuilder(column: $table.owner, builder: (column) => column);

  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<int> get position =>
      $composableBuilder(column: $table.position, builder: (column) => column);

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<int> get savedAt =>
      $composableBuilder(column: $table.savedAt, builder: (column) => column);

  GeneratedColumn<int> get validUntil => $composableBuilder(
      column: $table.validUntil, builder: (column) => column);
}

class $$CachedSignalsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CachedSignalsTable,
    CachedSignalRow,
    $$CachedSignalsTableFilterComposer,
    $$CachedSignalsTableOrderingComposer,
    $$CachedSignalsTableAnnotationComposer,
    $$CachedSignalsTableCreateCompanionBuilder,
    $$CachedSignalsTableUpdateCompanionBuilder,
    (
      CachedSignalRow,
      BaseReferences<_$AppDatabase, $CachedSignalsTable, CachedSignalRow>
    ),
    CachedSignalRow,
    PrefetchHooks Function()> {
  $$CachedSignalsTableTableManager(_$AppDatabase db, $CachedSignalsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CachedSignalsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CachedSignalsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CachedSignalsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> scope = const Value.absent(),
            Value<String> owner = const Value.absent(),
            Value<String> id = const Value.absent(),
            Value<int> position = const Value.absent(),
            Value<String> payload = const Value.absent(),
            Value<int> savedAt = const Value.absent(),
            Value<int> validUntil = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedSignalsCompanion(
            scope: scope,
            owner: owner,
            id: id,
            position: position,
            payload: payload,
            savedAt: savedAt,
            validUntil: validUntil,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String scope,
            required String owner,
            required String id,
            required int position,
            required String payload,
            required int savedAt,
            required int validUntil,
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedSignalsCompanion.insert(
            scope: scope,
            owner: owner,
            id: id,
            position: position,
            payload: payload,
            savedAt: savedAt,
            validUntil: validUntil,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$CachedSignalsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CachedSignalsTable,
    CachedSignalRow,
    $$CachedSignalsTableFilterComposer,
    $$CachedSignalsTableOrderingComposer,
    $$CachedSignalsTableAnnotationComposer,
    $$CachedSignalsTableCreateCompanionBuilder,
    $$CachedSignalsTableUpdateCompanionBuilder,
    (
      CachedSignalRow,
      BaseReferences<_$AppDatabase, $CachedSignalsTable, CachedSignalRow>
    ),
    CachedSignalRow,
    PrefetchHooks Function()>;
typedef $$CachedNewsTableCreateCompanionBuilder = CachedNewsCompanion Function({
  required String language,
  required String kind,
  required String id,
  required int position,
  required String payload,
  required int savedAt,
  Value<int> rowid,
});
typedef $$CachedNewsTableUpdateCompanionBuilder = CachedNewsCompanion Function({
  Value<String> language,
  Value<String> kind,
  Value<String> id,
  Value<int> position,
  Value<String> payload,
  Value<int> savedAt,
  Value<int> rowid,
});

class $$CachedNewsTableFilterComposer
    extends Composer<_$AppDatabase, $CachedNewsTable> {
  $$CachedNewsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get language => $composableBuilder(
      column: $table.language, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get kind => $composableBuilder(
      column: $table.kind, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get position => $composableBuilder(
      column: $table.position, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get payload => $composableBuilder(
      column: $table.payload, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get savedAt => $composableBuilder(
      column: $table.savedAt, builder: (column) => ColumnFilters(column));
}

class $$CachedNewsTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedNewsTable> {
  $$CachedNewsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get language => $composableBuilder(
      column: $table.language, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get kind => $composableBuilder(
      column: $table.kind, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get position => $composableBuilder(
      column: $table.position, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get payload => $composableBuilder(
      column: $table.payload, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get savedAt => $composableBuilder(
      column: $table.savedAt, builder: (column) => ColumnOrderings(column));
}

class $$CachedNewsTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedNewsTable> {
  $$CachedNewsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get language =>
      $composableBuilder(column: $table.language, builder: (column) => column);

  GeneratedColumn<String> get kind =>
      $composableBuilder(column: $table.kind, builder: (column) => column);

  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<int> get position =>
      $composableBuilder(column: $table.position, builder: (column) => column);

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<int> get savedAt =>
      $composableBuilder(column: $table.savedAt, builder: (column) => column);
}

class $$CachedNewsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CachedNewsTable,
    CachedNewsRow,
    $$CachedNewsTableFilterComposer,
    $$CachedNewsTableOrderingComposer,
    $$CachedNewsTableAnnotationComposer,
    $$CachedNewsTableCreateCompanionBuilder,
    $$CachedNewsTableUpdateCompanionBuilder,
    (
      CachedNewsRow,
      BaseReferences<_$AppDatabase, $CachedNewsTable, CachedNewsRow>
    ),
    CachedNewsRow,
    PrefetchHooks Function()> {
  $$CachedNewsTableTableManager(_$AppDatabase db, $CachedNewsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CachedNewsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CachedNewsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CachedNewsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> language = const Value.absent(),
            Value<String> kind = const Value.absent(),
            Value<String> id = const Value.absent(),
            Value<int> position = const Value.absent(),
            Value<String> payload = const Value.absent(),
            Value<int> savedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedNewsCompanion(
            language: language,
            kind: kind,
            id: id,
            position: position,
            payload: payload,
            savedAt: savedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String language,
            required String kind,
            required String id,
            required int position,
            required String payload,
            required int savedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedNewsCompanion.insert(
            language: language,
            kind: kind,
            id: id,
            position: position,
            payload: payload,
            savedAt: savedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$CachedNewsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CachedNewsTable,
    CachedNewsRow,
    $$CachedNewsTableFilterComposer,
    $$CachedNewsTableOrderingComposer,
    $$CachedNewsTableAnnotationComposer,
    $$CachedNewsTableCreateCompanionBuilder,
    $$CachedNewsTableUpdateCompanionBuilder,
    (
      CachedNewsRow,
      BaseReferences<_$AppDatabase, $CachedNewsTable, CachedNewsRow>
    ),
    CachedNewsRow,
    PrefetchHooks Function()>;
typedef $$CachedNotificationsTableCreateCompanionBuilder
    = CachedNotificationsCompanion Function({
  required String owner,
  required String language,
  required String id,
  required int position,
  required String payload,
  required int savedAt,
  Value<int> rowid,
});
typedef $$CachedNotificationsTableUpdateCompanionBuilder
    = CachedNotificationsCompanion Function({
  Value<String> owner,
  Value<String> language,
  Value<String> id,
  Value<int> position,
  Value<String> payload,
  Value<int> savedAt,
  Value<int> rowid,
});

class $$CachedNotificationsTableFilterComposer
    extends Composer<_$AppDatabase, $CachedNotificationsTable> {
  $$CachedNotificationsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get owner => $composableBuilder(
      column: $table.owner, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get language => $composableBuilder(
      column: $table.language, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get position => $composableBuilder(
      column: $table.position, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get payload => $composableBuilder(
      column: $table.payload, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get savedAt => $composableBuilder(
      column: $table.savedAt, builder: (column) => ColumnFilters(column));
}

class $$CachedNotificationsTableOrderingComposer
    extends Composer<_$AppDatabase, $CachedNotificationsTable> {
  $$CachedNotificationsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get owner => $composableBuilder(
      column: $table.owner, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get language => $composableBuilder(
      column: $table.language, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get position => $composableBuilder(
      column: $table.position, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get payload => $composableBuilder(
      column: $table.payload, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get savedAt => $composableBuilder(
      column: $table.savedAt, builder: (column) => ColumnOrderings(column));
}

class $$CachedNotificationsTableAnnotationComposer
    extends Composer<_$AppDatabase, $CachedNotificationsTable> {
  $$CachedNotificationsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get owner =>
      $composableBuilder(column: $table.owner, builder: (column) => column);

  GeneratedColumn<String> get language =>
      $composableBuilder(column: $table.language, builder: (column) => column);

  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<int> get position =>
      $composableBuilder(column: $table.position, builder: (column) => column);

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<int> get savedAt =>
      $composableBuilder(column: $table.savedAt, builder: (column) => column);
}

class $$CachedNotificationsTableTableManager extends RootTableManager<
    _$AppDatabase,
    $CachedNotificationsTable,
    CachedNotificationRow,
    $$CachedNotificationsTableFilterComposer,
    $$CachedNotificationsTableOrderingComposer,
    $$CachedNotificationsTableAnnotationComposer,
    $$CachedNotificationsTableCreateCompanionBuilder,
    $$CachedNotificationsTableUpdateCompanionBuilder,
    (
      CachedNotificationRow,
      BaseReferences<_$AppDatabase, $CachedNotificationsTable,
          CachedNotificationRow>
    ),
    CachedNotificationRow,
    PrefetchHooks Function()> {
  $$CachedNotificationsTableTableManager(
      _$AppDatabase db, $CachedNotificationsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CachedNotificationsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CachedNotificationsTableOrderingComposer(
                  $db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CachedNotificationsTableAnnotationComposer(
                  $db: db, $table: table),
          updateCompanionCallback: ({
            Value<String> owner = const Value.absent(),
            Value<String> language = const Value.absent(),
            Value<String> id = const Value.absent(),
            Value<int> position = const Value.absent(),
            Value<String> payload = const Value.absent(),
            Value<int> savedAt = const Value.absent(),
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedNotificationsCompanion(
            owner: owner,
            language: language,
            id: id,
            position: position,
            payload: payload,
            savedAt: savedAt,
            rowid: rowid,
          ),
          createCompanionCallback: ({
            required String owner,
            required String language,
            required String id,
            required int position,
            required String payload,
            required int savedAt,
            Value<int> rowid = const Value.absent(),
          }) =>
              CachedNotificationsCompanion.insert(
            owner: owner,
            language: language,
            id: id,
            position: position,
            payload: payload,
            savedAt: savedAt,
            rowid: rowid,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ));
}

typedef $$CachedNotificationsTableProcessedTableManager = ProcessedTableManager<
    _$AppDatabase,
    $CachedNotificationsTable,
    CachedNotificationRow,
    $$CachedNotificationsTableFilterComposer,
    $$CachedNotificationsTableOrderingComposer,
    $$CachedNotificationsTableAnnotationComposer,
    $$CachedNotificationsTableCreateCompanionBuilder,
    $$CachedNotificationsTableUpdateCompanionBuilder,
    (
      CachedNotificationRow,
      BaseReferences<_$AppDatabase, $CachedNotificationsTable,
          CachedNotificationRow>
    ),
    CachedNotificationRow,
    PrefetchHooks Function()>;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$CachedQuotesTableTableManager get cachedQuotes =>
      $$CachedQuotesTableTableManager(_db, _db.cachedQuotes);
  $$CachedCandlesTableTableManager get cachedCandles =>
      $$CachedCandlesTableTableManager(_db, _db.cachedCandles);
  $$CacheMetaTableTableManager get cacheMeta =>
      $$CacheMetaTableTableManager(_db, _db.cacheMeta);
  $$CachedSignalsTableTableManager get cachedSignals =>
      $$CachedSignalsTableTableManager(_db, _db.cachedSignals);
  $$CachedNewsTableTableManager get cachedNews =>
      $$CachedNewsTableTableManager(_db, _db.cachedNews);
  $$CachedNotificationsTableTableManager get cachedNotifications =>
      $$CachedNotificationsTableTableManager(_db, _db.cachedNotifications);
}
