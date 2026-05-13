interface WeekRowProps {
  week: WeekRow;
  index: number;
  onOpen: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onLongPressStart: (e: React.PointerEvent) => void;
  onLongPressEnd: () => void;
}