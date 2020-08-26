import { Col, Row } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router';

import Message from 'components/Message';
import useRestApi from 'hooks/useRestApi';
import {
  getExperimentDetails,
  getTrialDetails,
  isNotFound,
} from 'services/api';
import { TrialDetailsParams } from 'services/types';
import { ExperimentDetails, TrialDetails } from 'types';

import Badge, { BadgeType } from '../components/Badge';
import Page from '../components/Page';
import Spinner from '../components/Spinner';
import usePolling from '../hooks/usePolling';

import css from './TrialDetails.module.scss';

interface Params {
  trialId: string;
}
// from=now-20s&to=now
const grafanaEmbedUrl = 'http://3.236.80.157:3000/d/govu5aZGk/dtrain-time-series-metrics?' +
 'viewPanel=17' +  // 17=netSent, 4=gpuUtil, 6-gpuMem
 '&orgId=1' +
 '&refresh=5s' +
 '&from=now-20s' +
 '&to=now' +
 '&var-Database=InfluxDB' +
 '&var-TrainingJob=training_job%7C%3D%7CALBERT_SQuAD_PyTorch_dist_2node' +
 '&var-NetworkInterface=ens3';

const TrialMetrics: React.FC = () => {
  const { trialId: trialIdParam } = useParams<Params>();
  const trialId = parseInt(trialIdParam);
  const [ experiment, setExperiment ] = useState<ExperimentDetails>();
  const [ trialResponse, triggerTrialRequest ] =
      useRestApi<TrialDetailsParams, TrialDetails>(getTrialDetails, { id: trialId });

  const trial = trialResponse.data;
  const experimentId = trial?.experimentId;

  const pollTrialDetails = useCallback(() => {
    triggerTrialRequest({ id: trialId });
  }, [ triggerTrialRequest, trialId ]);

  usePolling(pollTrialDetails);

  useEffect(() => {
    if (experimentId === undefined) return;
    getExperimentDetails({ id:experimentId })
      .then(experiment => setExperiment(experiment));
  }, [ experimentId ]);

  if (isNaN(trialId)) return <Message title={`Invalid Trial ID ${trialIdParam}`} />;
  if (trialResponse.error !== undefined) {
    const message = isNotFound(trialResponse.error) ?
      `Unable to find Trial ${trialId}` :
      `Unable to fetch Trial ${trialId}`;
    return <Message message={trialResponse.error.message} title={message} />;
  }
  if (!trial || !experiment) return <Spinner />;

  return (
    <Page
      backPath={`/det/experiments/${experimentId}`}
      breadcrumb={[
        { breadcrumbName: 'Experiments', path: '/det/experiments' },
        {
          breadcrumbName: `Experiment ${experimentId}`,
          path: `/det/experiments/${experimentId}`,
        },
        { breadcrumbName: `Trial ${trialId}`, path: `/det/trials/${trialId}` },
        { breadcrumbName: 'Metrics', path: `/det/trial-metrics/${trialId}` },
      ]}
      showDivider
      subTitle={<Badge state={trial?.state} type={BadgeType.State} />}
      title={`Trial ${trialId} Metrics`}>
      <Row className={css.topRow} gutter={[ 16, 16 ]}>
        <iframe frameBorder="0" height="600px" src={grafanaEmbedUrl} width="80%" />
      </Row>
    </Page>
  );
};

export default TrialMetrics;
