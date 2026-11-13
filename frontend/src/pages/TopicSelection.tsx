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
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-slate-400 bg-transparent">
        <Icons.Loader2 size={32} className="animate-spin text-indigo-500 mb-3" />
        <span className="text-sm font-medium">Loading practice topics...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 md:p-12 lg:p-16 max-w-7xl mx-auto text-slate-100 bg-transparent relative z-10">
      <div className="mb-8">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 shadow-md backdrop-blur-md transition-colors cursor-pointer"
        >
          <Icons.ArrowLeft size={14} /> Back to Home
        </button>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-10"
      >
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-2">
          <Icons.Compass size={13} />
          <span>Stage 1 • Conversation Practice Domain</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight text-white mb-3">
          Select a Topic
        </h1>
        <p className="text-slate-400 text-base md:text-lg max-w-2xl leading-relaxed">
          Choose the conversation domain you want to master against senior counterparts.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {topics.map((topic, index) => (
          <motion.div
            key={topic.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => handleSelectTopic(topic)}
            className="bg-slate-900/75 hover:bg-slate-850/90 border border-slate-800 hover:border-indigo-500/60 p-6 rounded-2xl cursor-pointer group flex flex-col h-full backdrop-blur-md transition-all duration-300 shadow-xl hover:shadow-indigo-500/10 hover:-translate-y-1"
          >
            <div className="w-12 h-12 rounded-xl bg-slate-800/90 border border-slate-700/60 flex items-center justify-center mb-4 text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white group-hover:border-indigo-500 transition-all shadow-sm">
              {getIcon(topic.icon)}
            </div>
            <h3 className="text-xl font-bold text-white group-hover:text-indigo-200 transition-colors mb-2">
              {topic.title}
            </h3>
            <p className="text-sm text-slate-400 leading-relaxed flex-1">
              {topic.description}
            </p>
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-indigo-400 font-semibold group-hover:text-indigo-300">
              <span>Select domain</span>
              <Icons.ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default TopicSelection;
