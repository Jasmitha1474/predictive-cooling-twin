import { Text } from '@react-three/drei';
import { Suspense, type ComponentProps } from 'react';

/**
 * drei <Text> suspends while troika loads its font (fetched from a CDN at runtime).
 * Each label gets its own Suspense boundary so the hall, pipes and animations render
 * immediately even if the font is slow or unreachable.
 */
export function Label(props: ComponentProps<typeof Text>) {
  return (
    <Suspense fallback={null}>
      <Text {...props} />
    </Suspense>
  );
}
