import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getTopics } from '../api/apiClient';
import { useStore } from '../store/useStore';
import * as Icons from 'lucide-react';

const TopicSelection: React.FC = () => {
  const [topics, setTopics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const setTopic = useStore((state) => state.setTopic);

  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const data = await getTopics();
        setTopics(data);
      } catch (error) {
        console.error('Failed to fetch topics', error);
      } finally {
        setLoading(false);
      }
    };
    fetchTopics();
  }, []);

  const handleSelectTopic = (topic: any) => {
    setTopic(topic);
    navigate('/roles');
  };

  const getIcon = (iconName: string) => {
    const IconComponent = (Icons as any)[iconName] || Icons.HelpCircle;
    return <IconComponent size={24} />;
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading topics...</div>;
  }

  return (
    <div className="min-h-screen p-8 md:p-16 max-w-7xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-12"
      >
        <h1 className="text-3xl md:text-5xl font-bold mb-4">Select a Topic</h1>
        <p className="text-slate-600 text-lg">Choose the type of conversation you want to practice.</p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {topics.map((topic, index) => (
          <motion.div
            key={topic.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => handleSelectTopic(topic)}
            className="glass-card p-6 rounded-2xl cursor-pointer group flex flex-col h-full"
          >
            <div className="w-12 h-12 rounded-xl bg-[var(--color-surface)] flex items-center justify-center mb-4 text-[var(--color-primary)] group-hover:bg-[var(--color-primary)] group-hover:text-slate-900 transition-colors">
              {getIcon(topic.icon)}
            </div>
            <h3 className="text-xl font-semibold mb-2">{topic.title}</h3>
            <p className="text-sm text-slate-600 flex-1">{topic.description}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default TopicSelection;
