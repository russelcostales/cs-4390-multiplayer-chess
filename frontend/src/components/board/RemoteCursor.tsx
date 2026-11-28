// RemoteCursor.tsx - the opponent's cursor dot, smoothed with react-spring
import { animated, useSpring } from '@react-spring/web';

interface RemoteCursorProps {
  x: number;
  y: number;
}

export default function RemoteCursor({ x, y }: RemoteCursorProps) {
  // updates only come in every ~50ms, the spring fills the gaps so it doesn't look jumpy
  const { left, top } = useSpring({ left: x * 100, top: y * 100, config: { tension: 300, friction: 30 } });

  return (
    <animated.div
      style={{
        position: 'absolute',
        left: left.to((v) => `${v}%`),
        top: top.to((v) => `${v}%`),
        width: 14,
        height: 14,
        marginLeft: -7,
        marginTop: -7,
        borderRadius: '50%',
        background: 'rgba(229, 119, 107, 0.85)',
        border: '2px solid #f4f4f4',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    />
  );
}