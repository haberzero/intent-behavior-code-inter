import unittest
from core.base.enums import PrivilegeLevel, RegistrationState


class TestPrivilegeLevel(unittest.TestCase):
    """测试 PrivilegeLevel 枚举"""

    def test_privilege_level_values(self):
        """验证 PrivilegeLevel 枚举的所有成员"""
        self.assertEqual(PrivilegeLevel.KERNEL.value, 1)
        self.assertEqual(PrivilegeLevel.EXTENSION.value, 2)
        self.assertEqual(PrivilegeLevel.UNAUTHORIZED.value, 3)

    def test_privilege_level_count(self):
        """验证 PrivilegeLevel 枚举成员数量"""
        members = list(PrivilegeLevel)
        self.assertEqual(len(members), 3)

    def test_privilege_level_names(self):
        """验证 PrivilegeLevel 枚举成员名称"""
        names = [m.name for m in PrivilegeLevel]
        self.assertIn("KERNEL", names)
        self.assertIn("EXTENSION", names)
        self.assertIn("UNAUTHORIZED", names)


class TestRegistrationState(unittest.TestCase):
    """测试 RegistrationState 枚举"""

    def test_registration_state_values(self):
        """验证 RegistrationState 枚举的所有成员"""
        self.assertEqual(RegistrationState.STAGE_1_BOOTSTRAP.value, 1)
        self.assertEqual(RegistrationState.STAGE_2_CORE_TYPES.value, 2)
        self.assertEqual(RegistrationState.STAGE_3_PLUGIN_METADATA.value, 3)
        self.assertEqual(RegistrationState.STAGE_4_PLUGIN_IMPL.value, 4)
        self.assertEqual(RegistrationState.STAGE_5_HYDRATION.value, 5)
        self.assertEqual(RegistrationState.STAGE_6_PRE_EVAL.value, 6)
        self.assertEqual(RegistrationState.STAGE_7_READY.value, 7)

    def test_registration_state_count(self):
        """验证 RegistrationState 枚举成员数量"""
        members = list(RegistrationState)
        self.assertEqual(len(members), 7)

    def test_registration_state_sequential(self):
        """验证 RegistrationState 值是连续的"""
        for i, state in enumerate(RegistrationState, start=1):
            self.assertEqual(state.value, i)

    def test_registration_state_names(self):
        """验证 RegistrationState 枚举成员名称"""
        names = [m.name for m in RegistrationState]
        self.assertIn("STAGE_1_BOOTSTRAP", names)
        self.assertIn("STAGE_2_CORE_TYPES", names)
        self.assertIn("STAGE_3_PLUGIN_METADATA", names)
        self.assertIn("STAGE_4_PLUGIN_IMPL", names)
        self.assertIn("STAGE_5_HYDRATION", names)
        self.assertIn("STAGE_6_PRE_EVAL", names)
        self.assertIn("STAGE_7_READY", names)

    def test_registration_state_stage_order(self):
        """验证 RegistrationState 的阶段顺序"""
        self.assertLess(
            RegistrationState.STAGE_1_BOOTSTRAP.value,
            RegistrationState.STAGE_2_CORE_TYPES.value
        )
        self.assertLess(
            RegistrationState.STAGE_6_PRE_EVAL.value,
            RegistrationState.STAGE_7_READY.value
        )


class TestEnumInheritance(unittest.TestCase):
    """测试枚举继承关系"""

    def test_privilege_level_is_enum(self):
        """验证 PrivilegeLevel 是 Enum"""
        from enum import Enum
        self.assertTrue(issubclass(PrivilegeLevel, Enum))

    def test_registration_state_is_enum(self):
        """验证 RegistrationState 是 Enum"""
        from enum import Enum
        self.assertTrue(issubclass(RegistrationState, Enum))


if __name__ == "__main__":
    unittest.main()
