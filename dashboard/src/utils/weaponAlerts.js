export function getWeaponAlertFromEvent(message) {
  if (
    message?.type !== "WEAPON_ALERT" ||
    typeof message.data?.weapon_detected !== "boolean"
  ) {
    return null;
  }

  return message.data;
}