/// نموذج بيانات المستخدم المعتمد
/// 
/// هذا الكلاس immutable (غير قابل للتعديل)
/// يمثل مستخدم مسجل في التطبيق
final class UserModel {
  // ═══════════════════════════════════════════════════════════
  // Constructor
  // ═══════════════════════════════════════════════════════════
  
  const UserModel({
    required this.id,
    required this.email,
    this.displayName,
    this.avatarUrl,
    this.createdAt,
  });
  
  // ═══════════════════════════════════════════════════════════
  // Properties - الخصائص
  // ═══════════════════════════════════════════════════════════
  
  /// معرف المستخدم الفريد
  final String id;
  
  /// البريد الإلكتروني
  final String email;
  
  /// الاسم المعروض (اختياري)
  final String? displayName;
  
  /// رابط صورة المستخدم (اختياري)
  final String? avatarUrl;
  
  /// تاريخ إنشاء الحساب (اختياري)
  final DateTime? createdAt;
  
  // ═══════════════════════════════════════════════════════════
  // JSON Serialization - التحويل من وإلى JSON
  // ═══════════════════════════════════════════════════════════
  
  /// إنشاء UserModel من JSON
  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
        id: json['id'] as String,
        email: json['email'] as String,
        displayName: json['displayName'] as String?,
        avatarUrl: json['avatarUrl'] as String?,
        createdAt: json['createdAt'] != null
            ? DateTime.parse(json['createdAt'] as String)
            : null,
      );
  
  /// تحويل UserModel إلى JSON
  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        if (displayName != null) 'displayName': displayName,
        if (avatarUrl != null) 'avatarUrl': avatarUrl,
        if (createdAt != null) 'createdAt': createdAt!.toIso8601String(),
      };
  
  // ═══════════════════════════════════════════════════════════
  // Copy With - إنشاء نسخة مع تعديلات
  // ═══════════════════════════════════════════════════════════
  
  /// إنشاء نسخة جديدة مع تعديل بعض الخصائص
  UserModel copyWith({
    String? id,
    String? email,
    String? displayName,
    String? avatarUrl,
    DateTime? createdAt,
  }) {
    return UserModel(
      id: id ?? this.id,
      email: email ?? this.email,
      displayName: displayName ?? this.displayName,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      createdAt: createdAt ?? this.createdAt,
    );
  }
  
  // ═══════════════════════════════════════════════════════════
  // Override Methods - تجاوز الدوال الأساسية
  // ═══════════════════════════════════════════════════════════
  
  @override
  String toString() => 'UserModel(id: $id, email: $email, displayName: $displayName)';
  
  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is UserModel && other.id == id && other.email == email;
  }
  
  @override
  int get hashCode => Object.hash(id, email);
}
