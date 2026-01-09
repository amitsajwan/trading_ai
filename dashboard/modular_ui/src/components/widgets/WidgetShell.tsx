import React from 'react'
import { useDispatch } from 'react-redux'
import { updateWidgetConfig } from '../../store/slices/uiSlice'

interface WidgetShellProps {
  id: string
  title?: string
  children: React.ReactNode
}

export const WidgetShell: React.FC<WidgetShellProps> = ({ id, title, children }) => {
  const dispatch = useDispatch()

  const move = (dy: number) => {
    dispatch(updateWidgetConfig({ id, config: { position: { x: 0, y: dy } } }))
    // Note: For simplicity this updates a delta; a proper implementation should reorder the widgets array.
  }

  const toggleVisible = () => {
    dispatch(updateWidgetConfig({ id, config: { visible: false } }))
  }

  return (
    <div className="relative" data-widget-id={id} data-testid={`widget-${id}`}>
      <div className="absolute right-2 top-2 flex space-x-1">
        <button aria-label={`move-up-${id}`} title="Move up" onClick={() => move(-1)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">▲</button>
        <button aria-label={`move-down-${id}`} title="Move down" onClick={() => move(1)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">▼</button>
        <button aria-label={`hide-${id}`} title="Hide widget" onClick={toggleVisible} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">✕</button>
      </div>

      <div>{children}</div>
    </div>
  )
}
