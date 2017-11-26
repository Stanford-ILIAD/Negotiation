# NOTE: using the task-specific Session
from sessions.session import Session

class RulebasedSession(Session):
    """Generic rule-based system framework.
    """
    def __init__(self, agent, kb, parser, generator, manager, state, sample_temperature=1.):
        super(RulebasedSession, self).__init__(agent)
        self.parser = parser
        self.generator = generator
        self.manager = manager
        self.state = state
        self.sample_temperature = sample_temperature
        self.used_templates = set()

    def receive(self, event):
        utterance = self.parser.parse(event, self.state)
        print 'receive:'
        print utterance
        self.state.update(self.partner, utterance)

    def has_done(self, intent):
        return intent in self.state.done

    def retrieve_response_template(self, tag, **kwargs):
        context_tag = self.state.partner_act if self.state.partner_act != 'unknown' else None
        context = self.state.partner_template
        print 'retrieve:', tag
        template = self.generator.retrieve(context, tag=tag, context_tag=context_tag, used_templates=self.used_templates, T=self.sample_temperature, **kwargs)
        if template is None:
            return None
        self.used_templates.add(template['id'])
        template = template.to_dict()
        template['source'] = 'rule'
        return template

    def message(self, utterance):
        self.state.update(self.agent, utterance)
        metadata = {
                'sent': utterance.to_dict(),
                'received': self.state.utterance[self.partner].to_dict()
                }
        return super(RulebasedSession, self).message(utterance.text, metadata=metadata)