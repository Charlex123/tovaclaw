import { useState } from "react";
import { CheckSquare, Square, Circle } from "lucide-react";

interface TodoItem {
  id: string;
  title: string;
  completed: boolean;
  priority?: "high" | "medium" | "low";
  due?: string;
}

const priorityColors = {
  high: "text-red-400 bg-red-400/10",
  medium: "text-amber-400 bg-amber-400/10",
  low: "text-green-400 bg-green-400/10",
};

export default function TodoCard({ data }: { data: { todos: TodoItem[] } }) {
  const [todos, setTodos] = useState(data.todos ?? []);

  const toggleTodo = (id: string) => {
    setTodos((prev) =>
      prev.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t))
    );
  };

  return (
    <div className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5 bg-white/[0.01]">
        <CheckSquare className="w-4 h-4 text-cyan-400" />
        <span className="text-sm text-white font-medium">Tasks</span>
        <span className="text-xs text-neutral-600 ml-auto">
          {todos.filter((t) => t.completed).length}/{todos.length} done
        </span>
      </div>
      <div className="divide-y divide-white/5">
        {todos.map((todo) => (
          <div
            key={todo.id}
            className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors"
          >
            <button
              onClick={() => toggleTodo(todo.id)}
              className="shrink-0 text-neutral-500 hover:text-cyan-400 transition-colors"
            >
              {todo.completed ? (
                <CheckSquare className="w-4 h-4 text-cyan-400" />
              ) : (
                <Square className="w-4 h-4" />
              )}
            </button>
            <span
              className={`text-sm flex-1 ${
                todo.completed
                  ? "text-neutral-600 line-through"
                  : "text-neutral-200"
              }`}
            >
              {todo.title}
            </span>
            {todo.priority && (
              <span
                className={`flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full ${
                  priorityColors[todo.priority]
                }`}
              >
                <Circle className="w-2 h-2 fill-current" />
                {todo.priority}
              </span>
            )}
            {todo.due && (
              <span className="text-xs text-neutral-600">{todo.due}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
